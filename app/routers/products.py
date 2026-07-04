from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app import (
    PaginationParams,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    create_product,
    delete_product,
    get_admin_user,
    get_db,
    get_or_404,
    get_products,
    pagination_params,
    update_product,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    category: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    db: Prisma = Depends(get_db),
):
    products, total = await get_products(db, category=category, **pagination)
    return ProductListResponse(
        products=[ProductResponse.model_validate(p) for p in products],
        total=total,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product_by_id(
    product_id: str,
    db: Prisma = Depends(get_db),
):
    product = await get_or_404(db, "product", product_id)
    return ProductResponse.model_validate(product)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_product(
    data: ProductCreate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    product = await create_product(db, data.model_dump())
    return ProductResponse.model_validate(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product_by_id(
    product_id: str,
    data: ProductUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "product", product_id)
    updated = await update_product(
        db, product_id, data.model_dump(exclude_none=True)
    )
    return ProductResponse.model_validate(updated)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_by_id(
    product_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "product", product_id)
    await delete_product(db, product_id)
