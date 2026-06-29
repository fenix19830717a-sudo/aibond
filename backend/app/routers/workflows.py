from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import hashlib
import hmac

from app.database import get_db
from app.models.models import Workflow, WorkflowInstance
from app.security import get_current_user_id, get_current_actor, rate_limit
from app.workflows.engine import WorkflowEngine
from app.workflows.templates import get_all_templates, get_template_by_id, PRESET_TEMPLATES

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    owner_id: str = Field(..., min_length=1)
    group_id: str | None = Field(None, min_length=1)
    definition: dict | None = None
    trigger_type: str = Field("manual", pattern=r"^(manual|message|schedule|webhook|event)$")

class CreateFromTemplateRequest(BaseModel):
    template_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    owner_id: str = Field(..., min_length=1)
    group_id: str | None = Field(None, min_length=1)

class UpdateDefinitionRequest(BaseModel):
    definition: dict

@router.post("/")
async def create_workflow(req: CreateWorkflowRequest, request: Request, uid: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    await rate_limit(request, limit=20, window=60)

    # 强制 owner_id = 当前登录用户
    if req.owner_id != uid:
        raise HTTPException(status_code=403, detail="Cannot create workflow for another user")

    workflow = Workflow(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        owner_id=uid,
        group_id=req.group_id,
        definition=req.definition or {"nodes": [], "edges": []},
        trigger_type=req.trigger_type,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "definition": workflow.definition,
        "trigger_type": workflow.trigger_type,
    }

@router.get("/")
async def list_workflows(uid: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    # 仅返回当前用户拥有的 Workflow
    result = await db.execute(select(Workflow).where(Workflow.is_active == True, Workflow.owner_id == uid))
    workflows = result.scalars().all()

    return [{
        "id": w.id,
        "name": w.name,
        "description": w.description,
        "trigger_type": w.trigger_type,
        "group_id": w.group_id,
        "created_at": str(w.created_at),
    } for w in workflows]

@router.get("/templates")
async def list_workflow_templates():
    """返回所有 12 个预置 Workflow 模板"""
    templates = get_all_templates()
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "category": t["category"],
            "icon": t["icon"],
            "trigger_type": t["trigger_type"],
            "trigger_config": t.get("trigger_config", {}),
            "node_count": len(t["definition"].get("nodes", [])),
            "edge_count": len(t["definition"].get("edges", [])),
        }
        for t in templates
    ]


@router.post("/create-from-template")
async def create_workflow_from_template(
    req: CreateFromTemplateRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """从预置模板创建 Workflow"""
    await rate_limit(request, limit=20, window=60)

    # 强制 owner_id = 当前登录用户
    if req.owner_id != uid:
        raise HTTPException(status_code=403, detail="Cannot create workflow for another user")

    template = get_template_by_id(req.template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found")

    workflow = Workflow(
        id=str(uuid.uuid4()),
        name=req.name,
        description=template.get("description", ""),
        owner_id=uid,
        group_id=req.group_id,
        definition=template.get("definition", {"nodes": [], "edges": []}),
        trigger_type=template.get("trigger_type", "manual"),
        trigger_config=template.get("trigger_config", {}),
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "trigger_config": workflow.trigger_config,
        "template_id": req.template_id,
        "node_count": len(template.get("definition", {}).get("nodes", [])),
        "edge_count": len(template.get("definition", {}).get("edges", [])),
    }


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, actor: tuple[str, str] = Depends(get_current_actor), db: AsyncSession = Depends(get_db)):
    actor_id, actor_type = actor

    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Only the owner user can view the workflow
    if actor_type != "user" or workflow.owner_id != actor_id:
        raise HTTPException(status_code=403, detail="Only the owner can view this workflow")

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "definition": workflow.definition,
        "trigger_type": workflow.trigger_type,
        "trigger_config": workflow.trigger_config,
        "group_id": workflow.group_id,
    }

@router.put("/{workflow_id}/definition")
async def update_workflow_definition(workflow_id: str, req: UpdateDefinitionRequest, request: Request, actor: tuple[str, str] = Depends(get_current_actor), db: AsyncSession = Depends(get_db)):
    await rate_limit(request, limit=30, window=60)

    actor_id, actor_type = actor

    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Only the owner user can update the workflow
    if actor_type != "user" or workflow.owner_id != actor_id:
        raise HTTPException(status_code=403, detail="Only the owner can update this workflow")

    workflow.definition = req.definition
    await db.commit()

    return {"status": "ok"}




@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: Request, actor: tuple[str, str] = Depends(get_current_actor), db: AsyncSession = Depends(get_db)):
    await rate_limit(request, limit=10, window=60)

    actor_id, actor_type = actor

    # Verify workflow exists
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Only the owner user can run the workflow
    if actor_type != "user" or workflow.owner_id != actor_id:
        raise HTTPException(status_code=403, detail="Only the owner can run this workflow")

    # Execute workflow using the engine
    engine = WorkflowEngine(db)
    engine_result = await engine.run(workflow_id)

    if "error" in engine_result:
        raise HTTPException(status_code=400, detail=engine_result["error"])

    return engine_result

@router.post("/{workflow_id}/webhook")
async def webhook_trigger(workflow_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Receive external webhook callback and trigger workflow execution.

    Accepts any JSON payload from an external webhook and starts the
    workflow identified by workflow_id. The webhook payload is injected
    into the workflow context as `webhook_payload`.

    Security: Requires X-Webhook-Signature header (HMAC-SHA256) matching
    the workflow's webhook_secret stored in trigger_config.
    """
    # Parse webhook body
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Verify workflow exists
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Verify webhook signature
    trigger_config = workflow.trigger_config or {}
    webhook_secret = trigger_config.get("webhook_secret", "")
    signature = request.headers.get("X-Webhook-Signature", "")

    if not webhook_secret:
        # No secret configured — reject to prevent unauthorized triggering
        raise HTTPException(status_code=403, detail="Webhook secret not configured for this workflow")

    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Signature header")

    # Compute expected HMAC-SHA256 of the raw body
    raw_body = await request.body()
    expected_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Execute workflow using the engine
    engine = WorkflowEngine(db)
    engine_result = await engine.run(workflow_id)

    if "error" in engine_result:
        raise HTTPException(status_code=400, detail=engine_result["error"])

    return {
        "webhook_received": True,
        "payload": body,
        "workflow_result": engine_result,
    }
