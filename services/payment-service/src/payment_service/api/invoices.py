from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.api.deps import get_db, require_permission
from payment_service.domain.access import can_see_payment, is_manager, not_found
from payment_service.domain.invoices import invoice_view, render_html
from payment_service.infra.models import Invoice

router = APIRouter(prefix="/v1")


async def _visible(db: AsyncSession, principal: Principal, invoice_id: str) -> Invoice:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None or not can_see_payment(principal, tenant_id=invoice.tenant_id, user_id=invoice.user_id):
        raise not_found("Invoice")
    return invoice


@router.get("/invoices")
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("invoices:read"))],
    user_id: str | None = None,
    payment_id: str | None = None,
) -> dict:
    query = select(Invoice).where(Invoice.tenant_id == principal.tenant_id)
    if is_manager(principal):
        if user_id:
            query = query.where(Invoice.user_id == user_id)
    else:
        query = query.where(Invoice.user_id == principal.user_id)
    if payment_id:
        query = query.where(Invoice.payment_id == payment_id)
    rows = await db.scalars(query.order_by(Invoice.issued_at.desc(), Invoice.id.desc()).limit(200))
    return {"data": [invoice_view(i) for i in rows]}


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("invoices:read"))],
) -> dict:
    return invoice_view(await _visible(db, principal, invoice_id))


@router.get("/invoices/{invoice_id}/document", response_class=HTMLResponse)
async def get_invoice_document(
    invoice_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("invoices:read"))],
) -> HTMLResponse:
    invoice = await _visible(db, principal, invoice_id)
    return HTMLResponse(render_html(invoice), headers={"Cache-Control": "private, no-store"})
