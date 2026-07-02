from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app import (
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartResponse,
    add_to_cart,
    clear_cart,
    get_cart,
    get_current_user,
    get_db,
    get_product,
    remove_cart_item,
    update_cart_item,
)

router = APIRouter(prefix="/cart", tags=["Cart"])


def _compute_totals(items):
    subtotal = 0.0
    for item in items:
        if item.type == "RENT":
            subtotal += item.product.price * item.quantity * item.rentalDays
        else:
            subtotal += item.product.price * item.quantity
    delivery_fee = 0.0 if subtotal >= 2000 else 150.0
    return subtotal, delivery_fee


@router.get("", response_model=CartResponse)
async def get_my_cart(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    items = await get_cart(db, current_user.id)
    subtotal, delivery_fee = _compute_totals(items)
    return CartResponse(
        items=[CartItemResponse.model_validate(i) for i in items],
        total=round(subtotal, 2),
        deliveryFee=delivery_fee,
        grandTotal=round(subtotal + delivery_fee, 2),
    )


@router.post(
    "", response_model=CartItemResponse, status_code=status.HTTP_201_CREATED
)
async def add_item_to_cart(
    data: CartItemCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    product = await get_product(db, data.productId)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    item = await add_to_cart(db, current_user.id, data.model_dump())
    full_item = await db.cartitem.find_unique(
        where={"id": item.id}, include={"product": True}
    )
    return CartItemResponse.model_validate(full_item)


@router.put("/{item_id}", response_model=CartItemResponse)
async def update_cart_item_by_id(
    item_id: str,
    data: CartItemUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    item = await db.cartitem.find_unique(
        where={"id": item_id}, include={"product": True}
    )
    if not item or item.userId != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    updated = await update_cart_item(
        db, item_id, data.model_dump(exclude_none=True)
    )
    full = await db.cartitem.find_unique(
        where={"id": updated.id}, include={"product": True}
    )
    return CartItemResponse.model_validate(full)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_cart(
    item_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    item = await db.cartitem.find_unique(where={"id": item_id})
    if not item or item.userId != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await remove_cart_item(db, item_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_my_cart(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    await clear_cart(db, current_user.id)
