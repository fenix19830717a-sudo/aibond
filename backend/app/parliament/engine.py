"""Parliament Engine - Multi-agent consensus voting, deliberation, and escalation.

Core design (from AgentParliament concept):
1. Multiple cheap models (DeepSeek, GLM, MiniMax) perform independent analysis
2. Cross-validation through mutual review and voting
3. Confidence-based escalation: low-confidence results escalate to higher-tier agents
4. Claude/arbiter as final decision-maker when deadlocked

Consensus types:
- majority: >50% approval
- supermajority: >=2/3 approval
- unanimous: 100% approval
- weighted: weighted by agent tier + reliability_score
"""

import uuid
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Parliament, ParliamentMember, ParliamentProposal, ParliamentVote,
    Agent, Group, GroupMember, Message,
)
from app.websocket.manager import ws_manager


# Tier multipliers for weighted voting
TIER_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.0}

# Consensus thresholds
CONSENSUS_THRESHOLDS = {
    "majority": 0.5,
    "supermajority": 2 / 3,
    "unanimous": 1.0,
    "weighted": 0.5,  # weighted compares weighted sum
}


class ParliamentEngine:
    """Manages the full lifecycle of an Agent Parliament session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Creation ──

    async def create_parliament(
        self,
        group_id: str,
        title: str,
        topic: str,
        created_by: str,
        consensus_type: str = "majority",
        min_confidence: float = 0.6,
        max_rounds: int = 3,
    ) -> dict:
        """Create a new parliament session and auto-invite group agents."""
        # Verify group exists
        group_result = await self.db.execute(select(Group).where(Group.id == group_id))
        group = group_result.scalar_one_or_none()
        if not group:
            return {"error": "Group not found", "status": "failed"}

        parliament = Parliament(
            id=str(uuid.uuid4()),
            group_id=group_id,
            title=title,
            topic=topic,
            status="deliberating",
            consensus_type=consensus_type,
            min_confidence=min_confidence,
            max_rounds=max_rounds,
            created_by=created_by,
        )
        self.db.add(parliament)

        # Auto-invite all agents in the group
        agent_members = await self.db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.agent_id.isnot(None),
            )
        )
        agent_members = agent_members.scalars().all()

        for am in agent_members:
            agent_result = await self.db.execute(
                select(Agent).where(Agent.id == am.agent_id, Agent.is_active == True)
            )
            agent = agent_result.scalar_one_or_none()
            if not agent:
                continue

            # Determine role based on agent_role field
            role = agent.agent_role if agent.agent_role in (
                "arbiter", "reviewer", "analyst", "executor", "observer"
            ) else "voter"

            # Map agent_role to parliament role
            role_map = {
                "arbiter": "speaker",
                "reviewer": "reviewer",
                "analyst": "analyst",
                "executor": "voter",
                "observer": "observer",
            }
            parliament_role = role_map.get(agent.agent_role, "voter")

            weight = TIER_WEIGHTS.get(agent.tier, 1.0) * agent.reliability_score

            member = ParliamentMember(
                id=str(uuid.uuid4()),
                parliament_id=parliament.id,
                agent_id=agent.id,
                role=parliament_role,
                tier=agent.tier,
                weight=weight,
            )
            self.db.add(member)

        await self.db.commit()
        await self.db.refresh(parliament)

        return await self._parliament_to_dict(parliament)

    # ── Deliberation Round ──

    async def deliberate(self, parliament_id: str) -> dict:
        """Execute one deliberation round: collect proposals, vote, tally, check consensus."""
        parliament = await self._get_parliament(parliament_id)
        if not parliament:
            return {"error": "Parliament not found", "status": "failed"}

        if parliament.status not in ("deliberating", "voting"):
            return {"error": f"Parliament is {parliament.status}, cannot deliberate", "status": "failed"}

        # Increment round
        parliament.round_count += 1
        parliament.status = "deliberating"
        round_num = parliament.round_count

        # Get all active members
        members = await self._get_members(parliament_id)
        if len(members) < 2:
            parliament.status = "deadlocked"
            await self.db.commit()
            return {"error": "Need at least 2 members for deliberation", "status": "deadlocked"}

        await self.db.commit()

        return {
            "status": "deliberating",
            "parliament_id": parliament_id,
            "round": round_num,
            "max_rounds": parliament.max_rounds,
            "member_count": len(members),
            "members": [
                {"agent_id": m.agent_id, "role": m.role, "tier": m.tier, "weight": m.weight}
                for m in members
            ],
        }

    # ── Proposals ──

    async def submit_proposal(
        self,
        parliament_id: str,
        proposer_id: str,
        content: str,
        confidence: float = 0.5,
    ) -> dict:
        """Submit a proposal to the parliament."""
        parliament = await self._get_parliament(parliament_id)
        if not parliament:
            return {"error": "Parliament not found", "status": "failed"}

        if parliament.status not in ("deliberating",):
            return {"error": "Parliament is not accepting proposals", "status": "failed"}

        # Verify proposer is a member
        member = await self._get_member(parliament_id, proposer_id)
        if not member:
            return {"error": "Proposer is not a parliament member", "status": "failed"}

        proposal = ParliamentProposal(
            id=str(uuid.uuid4()),
            parliament_id=parliament_id,
            proposer_id=proposer_id,
            round_number=parliament.round_count,
            content=content,
            confidence=confidence,
        )
        self.db.add(proposal)
        await self.db.commit()
        await self.db.refresh(proposal)

        return {
            "id": proposal.id,
            "parliament_id": parliament_id,
            "proposer_id": proposer_id,
            "round": proposal.round_number,
            "content": proposal.content,
            "confidence": proposal.confidence,
        }

    # ── Voting ──

    async def cast_vote(
        self,
        parliament_id: str,
        proposal_id: str,
        voter_id: str,
        vote: str,
        confidence: float = 0.5,
        reasoning: str = "",
    ) -> dict:
        """Cast a vote on a proposal."""
        parliament = await self._get_parliament(parliament_id)
        if not parliament:
            return {"error": "Parliament not found", "status": "failed"}

        if vote not in ("approve", "reject", "abstain"):
            return {"error": "Invalid vote, must be approve/reject/abstain", "status": "failed"}

        # Verify proposal exists and belongs to this parliament
        prop_result = await self.db.execute(
            select(ParliamentProposal).where(
                ParliamentProposal.id == proposal_id,
                ParliamentProposal.parliament_id == parliament_id,
            )
        )
        proposal = prop_result.scalar_one_or_none()
        if not proposal:
            return {"error": "Proposal not found", "status": "failed"}

        # Verify voter is a member
        member = await self._get_member(parliament_id, voter_id)
        if not member:
            return {"error": "Voter is not a parliament member", "status": "failed"}

        # Check if already voted this round
        existing = await self.db.execute(
            select(ParliamentVote).where(
                ParliamentVote.parliament_id == parliament_id,
                ParliamentVote.proposal_id == proposal_id,
                ParliamentVote.voter_id == voter_id,
                ParliamentVote.round_number == parliament.round_count,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "Already voted on this proposal this round", "status": "failed"}

        vote_record = ParliamentVote(
            id=str(uuid.uuid4()),
            parliament_id=parliament_id,
            proposal_id=proposal_id,
            voter_id=voter_id,
            round_number=parliament.round_count,
            vote=vote,
            confidence=confidence,
            reasoning=reasoning,
        )
        self.db.add(vote_record)

        # Transition to voting if still deliberating
        if parliament.status == "deliberating":
            parliament.status = "voting"

        await self.db.commit()

        return {
            "id": vote_record.id,
            "proposal_id": proposal_id,
            "voter_id": voter_id,
            "vote": vote,
            "confidence": confidence,
            "round": parliament.round_count,
        }

    # ── Tally & Consensus ──

    async def tally_votes(self, parliament_id: str) -> dict:
        """Tally all votes for the current round and check consensus."""
        parliament = await self._get_parliament(parliament_id)
        if not parliament:
            return {"error": "Parliament not found", "status": "failed"}

        round_num = parliament.round_count
        members = await self._get_members(parliament_id)

        # Get all proposals for this round
        prop_result = await self.db.execute(
            select(ParliamentProposal).where(
                ParliamentProposal.parliament_id == parliament_id,
                ParliamentProposal.round_number == round_num,
            )
        )
        proposals = prop_result.scalars().all()

        if not proposals:
            return {"error": "No proposals in current round", "status": "failed"}

        results = []
        for proposal in proposals:
            # Get all votes for this proposal
            vote_result = await self.db.execute(
                select(ParliamentVote).where(
                    ParliamentVote.proposal_id == proposal.id,
                    ParliamentVote.round_number == round_num,
                )
            )
            votes = vote_result.scalars().all()

            tally = self._calculate_tally(votes, members, parliament.consensus_type)
            tally["proposal_id"] = proposal.id
            tally["proposer_id"] = proposal.proposer_id
            tally["content"] = proposal.content
            results.append(tally)

        # Check consensus
        consensus_result = self._check_consensus(results, parliament)

        # Update parliament status
        if consensus_result["reached"]:
            parliament.status = "consensus_reached"
            parliament.resolution = consensus_result
            parliament.resolved_at = datetime.now(timezone.utc)
        elif parliament.round_count >= parliament.max_rounds:
            # Check if escalation is possible
            if await self._can_escalate(parliament_id):
                parliament.status = "escalated"
            else:
                parliament.status = "deadlocked"
        else:
            parliament.status = "deliberating"

        # Update agent reliability scores based on voting alignment
        await self._update_reliability_scores(parliament_id, results, members)

        await self.db.commit()

        return {
            "parliament_id": parliament_id,
            "round": round_num,
            "status": parliament.status,
            "consensus_type": parliament.consensus_type,
            "consensus_reached": consensus_result["reached"],
            "proposals": results,
            "resolution": consensus_result if consensus_result["reached"] else None,
        }

    # ── Escalation ──

    async def escalate(self, parliament_id: str) -> dict:
        """Escalate to higher-tier agents or arbiter."""
        parliament = await self._get_parliament(parliament_id)
        if not parliament:
            return {"error": "Parliament not found", "status": "failed"}

        if parliament.status != "escalated" and not await self._can_escalate(parliament_id):
            return {"error": "Cannot escalate further", "status": "failed"}

        members = await self._get_members(parliament_id)

        # Find the highest-tier agent (arbiter)
        arbiter = None
        for m in members:
            if m.role == "speaker" or m.role == "arbiter":
                arbiter = m
                break
        if not arbiter:
            # Fallback: highest tier member
            members_sorted = sorted(members, key=lambda m: (m.tier, m.weight), reverse=True)
            arbiter = members_sorted[0] if members_sorted else None

        if not arbiter:
            parliament.status = "deadlocked"
            await self.db.commit()
            return {"error": "No arbiter available for escalation", "status": "deadlocked"}

        # Get all previous proposals and votes
        prev_proposals = await self.db.execute(
            select(ParliamentProposal).where(
                ParliamentProposal.parliament_id == parliament_id,
            )
        )
        proposals = prev_proposals.scalars().all()

        # Notify arbiter via WebSocket
        decision_request = {
            "type": "arbiter_decision_request",
            "parliament_id": parliament_id,
            "title": parliament.title,
            "topic": parliament.topic,
            "rounds": parliament.round_count,
            "proposals": [
                {"id": p.id, "content": p.content[:500], "proposer_id": p.proposer_id}
                for p in proposals
            ],
        }
        await ws_manager.send_to_agent(arbiter.agent_id, decision_request)

        # Create system message to record the escalation
        sys_msg = Message(
            id=str(uuid.uuid4()),
            group_id=parliament.group_id,
            sender_type="system",
            msg_type="workflow_trigger",
            content=f"议会 '{parliament.title}' 已升级至仲裁者，等待最终决策",
            msg_metadata={"event": "parliament_escalated", "parliament_id": parliament_id, "arbiter_id": arbiter.agent_id},
        )
        self.db.add(sys_msg)

        # Arbiter makes final decision
        parliament.status = "resolved"
        parliament.resolution = {
            "method": "arbiter_escalation",
            "arbiter_id": arbiter.agent_id,
            "arbiter_role": arbiter.role,
            "arbiter_tier": arbiter.tier,
            "previous_rounds": parliament.round_count,
            "proposals_reviewed": len(proposals),
            "reason": "低置信度共识触发升级，仲裁者做出最终决策",
        }
        parliament.resolved_at = datetime.now(timezone.utc)
        await self.db.commit()

        return {
            "parliament_id": parliament_id,
            "status": "resolved",
            "arbiter_id": arbiter.agent_id,
            "resolution": parliament.resolution,
        }

    # ── Resolution ──

    async def resolve(self, parliament_id: str, resolution: dict) -> dict:
        """Manually resolve a parliament (e.g., by human admin)."""
        parliament = await self._get_parliament(parliament_id)
        if not parliament:
            return {"error": "Parliament not found", "status": "failed"}

        parliament.status = "resolved"
        parliament.resolution = resolution
        parliament.resolved_at = datetime.now(timezone.utc)
        await self.db.commit()

        return {
            "parliament_id": parliament_id,
            "status": "resolved",
            "resolution": resolution,
        }

    # ── Internal Helpers ──

    async def _get_parliament(self, parliament_id: str) -> Optional[Parliament]:
        result = await self.db.execute(
            select(Parliament).where(Parliament.id == parliament_id)
        )
        return result.scalar_one_or_none()

    async def _get_members(self, parliament_id: str) -> list:
        result = await self.db.execute(
            select(ParliamentMember).where(
                ParliamentMember.parliament_id == parliament_id,
            )
        )
        return result.scalars().all()

    async def _get_member(self, parliament_id: str, agent_id: str) -> Optional[ParliamentMember]:
        result = await self.db.execute(
            select(ParliamentMember).where(
                ParliamentMember.parliament_id == parliament_id,
                ParliamentMember.agent_id == agent_id,
            )
        )
        return result.scalar_one_or_none()

    def _calculate_weighted_vote(self, vote: str, member: ParliamentMember) -> float:
        """Calculate the weighted value of a vote."""
        if vote == "approve":
            return member.weight
        elif vote == "reject":
            return -member.weight
        else:  # abstain
            return 0.0

    def _calculate_tally(
        self,
        votes: list[ParliamentVote],
        members: list[ParliamentMember],
        consensus_type: str,
    ) -> dict:
        """Calculate vote tally for a proposal."""
        total_members = len(members)
        total_voters = len(votes)

        approve_count = sum(1 for v in votes if v.vote == "approve")
        reject_count = sum(1 for v in votes if v.vote == "reject")
        abstain_count = sum(1 for v in votes if v.vote == "abstain")

        # Build member weight lookup
        weight_map = {m.agent_id: m.weight for m in members}

        # Weighted calculation
        weighted_approve = sum(
            weight_map.get(v.voter_id, 1.0) for v in votes if v.vote == "approve"
        )
        weighted_reject = sum(
            weight_map.get(v.voter_id, 1.0) for v in votes if v.vote == "reject"
        )
        total_weight = sum(weight_map.values())

        # Average confidence
        confidences = [v.confidence for v in votes]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Approval ratio
        if consensus_type == "weighted":
            approval_ratio = weighted_approve / total_weight if total_weight > 0 else 0
        else:
            # Simple count-based
            approval_ratio = approve_count / total_voters if total_voters > 0 else 0

        return {
            "total_members": total_members,
            "total_voters": total_voters,
            "approve": approve_count,
            "reject": reject_count,
            "abstain": abstain_count,
            "weighted_approve": weighted_approve,
            "weighted_reject": weighted_reject,
            "total_weight": total_weight,
            "approval_ratio": round(approval_ratio, 4),
            "avg_confidence": round(avg_confidence, 4),
            "votes": [
                {
                    "voter_id": v.voter_id,
                    "vote": v.vote,
                    "confidence": v.confidence,
                    "reasoning": v.reasoning,
                }
                for v in votes
            ],
        }

    def _check_consensus(self, results: list[dict], parliament: Parliament) -> dict:
        """Check if consensus has been reached."""
        if not results:
            return {"reached": False, "reason": "No proposals to evaluate"}

        threshold = CONSENSUS_THRESHOLDS.get(parliament.consensus_type, 0.5)

        # Find the best proposal
        best = max(results, key=lambda r: (r["approval_ratio"], r["avg_confidence"]))

        reached = best["approval_ratio"] >= threshold

        # Check confidence threshold
        if reached and best["avg_confidence"] < parliament.min_confidence:
            return {
                "reached": False,
                "reason": f"Consensus reached but avg confidence ({best['avg_confidence']:.2f}) below threshold ({parliament.min_confidence})",
                "best_proposal": best,
                "needs_escalation": True,
            }

        if reached:
            return {
                "reached": True,
                "best_proposal_id": best["proposal_id"],
                "approval_ratio": best["approval_ratio"],
                "avg_confidence": best["avg_confidence"],
                "consensus_type": parliament.consensus_type,
                "winning_content": best["content"],
                "tally": best,
            }

        return {
            "reached": False,
            "reason": f"No proposal reached {threshold*100:.0f}% threshold",
            "best_approval_ratio": best["approval_ratio"],
            "best_proposal": best,
        }

    async def _can_escalate(self, parliament_id: str) -> bool:
        """Check if there are higher-tier agents available for escalation."""
        members = await self._get_members(parliament_id)
        if not members:
            return False

        # Check if there's an arbiter/speaker
        has_arbiter = any(m.role in ("speaker", "arbiter") for m in members)
        if has_arbiter:
            return True

        # Check if there are tier 3 agents
        current_max_tier = max(m.tier for m in members)
        return current_max_tier >= 3

    async def _update_reliability_scores(
        self,
        parliament_id: str,
        results: list[dict],
        members: list[ParliamentMember],
    ) -> None:
        """Update agent reliability scores based on voting alignment with consensus."""
        if not results:
            return

        best = max(results, key=lambda r: (r["approval_ratio"], r["avg_confidence"]))
        winning_votes = {v["voter_id"]: v["vote"] for v in best.get("votes", [])}

        for member in members:
            agent_result = await self.db.execute(
                select(Agent).where(Agent.id == member.agent_id)
            )
            agent = agent_result.scalar_one_or_none()
            if not agent:
                continue

            # Simple heuristic: agents who voted with the majority get a slight boost
            vote = winning_votes.get(member.agent_id)
            old_score = agent.reliability_score or 0.5

            if vote == "approve":
                # Voting with consensus: boost
                new_score = min(1.0, old_score + 0.02)
            elif vote == "reject":
                # Voting against consensus: slight penalty
                new_score = max(0.1, old_score - 0.01)
            else:
                # Abstain: no change
                new_score = old_score

            agent.reliability_score = new_score
            self.db.add(agent)

    async def _parliament_to_dict(self, parliament: Parliament) -> dict:
        """Convert parliament object to dict with members."""
        members = await self._get_members(parliament.id)
        return {
            "id": parliament.id,
            "group_id": parliament.group_id,
            "title": parliament.title,
            "topic": parliament.topic,
            "status": parliament.status,
            "consensus_type": parliament.consensus_type,
            "min_confidence": parliament.min_confidence,
            "round_count": parliament.round_count,
            "max_rounds": parliament.max_rounds,
            "resolution": parliament.resolution,
            "created_by": parliament.created_by,
            "created_at": str(parliament.created_at),
            "resolved_at": str(parliament.resolved_at) if parliament.resolved_at else None,
            "members": [
                {
                    "agent_id": m.agent_id,
                    "role": m.role,
                    "tier": m.tier,
                    "weight": m.weight,
                }
                for m in members
            ],
        }