"""Parliament API - Multi-agent consensus voting and deliberation endpoints.

Endpoints:
- POST   /api/parliaments                    Create parliament
- GET    /api/parliaments/{id}               Get parliament details
- GET    /api/parliaments/group/{group_id}   List parliaments for a group
- POST   /api/parliaments/{id}/deliberate    Start a deliberation round
- POST   /api/parliaments/{id}/proposals     Submit a proposal
- POST   /api/parliaments/{id}/votes         Cast a vote
- POST   /api/parliaments/{id}/tally         Tally votes and check consensus
- POST   /api/parliaments/{id}/escalate      Escalate to arbiter
- POST   /api/parliaments/{id}/resolve       Manually resolve
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.security import get_current_actor, rate_limit
from app.parliament.engine import ParliamentEngine

router = APIRouter(prefix="/api/parliaments", tags=["parliament"])


# ── Request Models ──

class CreateParliamentRequest(BaseModel):
    group_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field("", max_length=5000)
    consensus_type: str = Field("majority", pattern=r"^(majority|supermajority|unanimous|weighted)$")
    min_confidence: float = Field(0.6, ge=0.0, le=1.0)
    max_rounds: int = Field(3, ge=1, le=10)


class SubmitProposalRequest(BaseModel):
    proposer_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, max_length=10000)
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class CastVoteRequest(BaseModel):
    proposal_id: str = Field(..., min_length=1)
    voter_id: str = Field(..., min_length=1)
    vote: str = Field(..., pattern=r"^(approve|reject|abstain)$")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str = Field("", max_length=2000)


class ResolveRequest(BaseModel):
    resolution: dict = Field(default_factory=dict)


# ── Endpoints ──

@router.post("/")
async def create_parliament(
    req: CreateParliamentRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Create a new parliament session for multi-agent deliberation."""
    await rate_limit(request, limit=50, window=60)

    actor_id, actor_type = actor
    engine = ParliamentEngine(db)
    result = await engine.create_parliament(
        group_id=req.group_id,
        title=req.title,
        topic=req.topic,
        created_by=actor_id,
        consensus_type=req.consensus_type,
        min_confidence=req.min_confidence,
        max_rounds=req.max_rounds,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/")
async def list_parliaments(
    actor: tuple[str, str] = Depends(get_current_actor),
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all parliament sessions with pagination."""
    from app.models.models import Parliament

    if limit < 1 or limit > 100:
        limit = 20
    if offset < 0:
        offset = 0

    query = select(Parliament)
    if status:
        query = query.where(Parliament.status == status)
    query = query.order_by(Parliament.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    parliaments = result.scalars().all()

    return {
        "items": [{
            "id": p.id,
            "group_id": p.group_id,
            "title": p.title,
            "topic": p.topic,
            "status": p.status,
            "consensus_type": p.consensus_type,
            "round_count": p.round_count,
            "max_rounds": p.max_rounds,
            "created_by": p.created_by,
            "created_at": str(p.created_at),
            "resolved_at": str(p.resolved_at) if p.resolved_at else None,
        } for p in parliaments],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{parliament_id}")
async def get_parliament(
    parliament_id: str,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Get parliament details including members, proposals, and votes."""
    from app.models.models import Parliament, ParliamentMember, ParliamentProposal, ParliamentVote

    result = await db.execute(
        select(Parliament).where(Parliament.id == parliament_id)
    )
    parliament = result.scalar_one_or_none()
    if not parliament:
        raise HTTPException(status_code=404, detail="Parliament not found")

    # Get members
    members_result = await db.execute(
        select(ParliamentMember).where(ParliamentMember.parliament_id == parliament_id)
    )
    members = members_result.scalars().all()

    # Get proposals
    proposals_result = await db.execute(
        select(ParliamentProposal).where(
            ParliamentProposal.parliament_id == parliament_id
        ).order_by(ParliamentProposal.round_number, ParliamentProposal.created_at)
    )
    proposals = proposals_result.scalars().all()

    # Get votes
    votes_result = await db.execute(
        select(ParliamentVote).where(
            ParliamentVote.parliament_id == parliament_id
        ).order_by(ParliamentVote.round_number, ParliamentVote.created_at)
    )
    votes = votes_result.scalars().all()

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
            {"id": m.id, "agent_id": m.agent_id, "role": m.role, "tier": m.tier, "weight": m.weight}
            for m in members
        ],
        "proposals": [
            {
                "id": p.id, "proposer_id": p.proposer_id, "round": p.round_number,
                "content": p.content, "confidence": p.confidence, "status": p.status,
            }
            for p in proposals
        ],
        "votes": [
            {
                "id": v.id, "proposal_id": v.proposal_id, "voter_id": v.voter_id,
                "round": v.round_number, "vote": v.vote, "confidence": v.confidence,
                "reasoning": v.reasoning,
            }
            for v in votes
        ],
    }


@router.get("/group/{group_id}")
async def list_parliaments(
    group_id: str,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """List all parliaments for a group."""
    from app.models.models import Parliament

    result = await db.execute(
        select(Parliament).where(
            Parliament.group_id == group_id
        ).order_by(Parliament.created_at.desc())
    )
    parliaments = result.scalars().all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "topic": p.topic,
            "status": p.status,
            "consensus_type": p.consensus_type,
            "round_count": p.round_count,
            "max_rounds": p.max_rounds,
            "resolution": p.resolution,
            "created_at": str(p.created_at),
            "resolved_at": str(p.resolved_at) if p.resolved_at else None,
        }
        for p in parliaments
    ]


@router.post("/{parliament_id}/deliberate")
async def deliberate(
    parliament_id: str,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Start a new deliberation round."""
    await rate_limit(request, limit=50, window=60)

    engine = ParliamentEngine(db)
    result = await engine.deliberate(parliament_id)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{parliament_id}/proposals")
async def submit_proposal(
    parliament_id: str,
    req: SubmitProposalRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Submit a proposal to the parliament."""
    await rate_limit(request, limit=50, window=60)

    actor_id, actor_type = actor
    engine = ParliamentEngine(db)
    result = await engine.submit_proposal(
        parliament_id=parliament_id,
        proposer_id=actor_id,
        content=req.content,
        confidence=req.confidence,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{parliament_id}/votes")
async def cast_vote(
    parliament_id: str,
    req: CastVoteRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Cast a vote on a proposal."""
    await rate_limit(request, limit=30, window=60)

    actor_id, actor_type = actor
    engine = ParliamentEngine(db)
    result = await engine.cast_vote(
        parliament_id=parliament_id,
        proposal_id=req.proposal_id,
        voter_id=actor_id,
        vote=req.vote,
        confidence=req.confidence,
        reasoning=req.reasoning,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{parliament_id}/tally")
async def tally_votes(
    parliament_id: str,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Tally all votes and check if consensus has been reached."""
    await rate_limit(request, limit=50, window=60)

    engine = ParliamentEngine(db)
    result = await engine.tally_votes(parliament_id)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{parliament_id}/escalate")
async def escalate(
    parliament_id: str,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Escalate to higher-tier agents or arbiter for final decision."""
    await rate_limit(request, limit=10, window=60)

    engine = ParliamentEngine(db)
    result = await engine.escalate(parliament_id)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{parliament_id}/resolve")
async def resolve(
    parliament_id: str,
    req: ResolveRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Manually resolve a parliament."""
    await rate_limit(request, limit=10, window=60)

    engine = ParliamentEngine(db)
    result = await engine.resolve(parliament_id, req.resolution)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result