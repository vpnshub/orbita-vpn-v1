from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import sys
from loguru import logger
import aiosqlite

from pathlib import Path
root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from handlers.database import Database

router = APIRouter(
    prefix="/pspayments",
    tags=["pspayments"],
    responses={404: {"description": "Настройки не найдены"}},
)

async def get_db():
    return Database()

class PSPaymentsSettingsCreate(BaseModel):
    name: str = Field(..., description="Название настройки")
    shop_id: str = Field(..., description="ID магазина PSPayments")
    api_key: str = Field(..., description="API ключ PSPayments")
    api_secret_key: str = Field(..., description="API Secret ключ")
    description: Optional[str] = Field(None, description="Описание настройки")

class PSPaymentsSettingsDelete(BaseModel):
    shop_id: str = Field(..., description="ID магазина PSPayments для удаления")


@router.get("/", response_model=Dict)
async def get_pspayments_settings(db: Database = Depends(get_db)):
    """
    Получение активных настроек PSPayments
    """
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT id, name, shop_id, description, is_enable 
                FROM pspayments_settings 
                WHERE is_enable = 1 
                LIMIT 1
            """)
            settings = await cursor.fetchone()

            if not settings:
                raise HTTPException(status_code=404, detail="Активные настройки PSPayments не найдены")

            result = dict(settings)
            return {
                "id": result["id"],
                "name": result["name"],
                "shop_id": result["shop_id"],
                "description": result["description"],
                "is_enable": result["is_enable"] == 1
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении настроек PSPayments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Dict)
async def create_pspayments_settings(
        settings: PSPaymentsSettingsCreate,
        db: Database = Depends(get_db)
):
    """
    Добавление новых настроек PSPayments

    - **name**: Название настройки
    - **shop_id**: ID магазина PSPayments
    - **api_key**: API ключ PSPayments
    - **api_secret_key**: API ключ PSPayments
    - **description**: Описание настройки (опционально)
    """
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                "UPDATE yookassa_settings SET is_enable = 0 WHERE is_enable = 1"
            )

            await conn.execute("""
                INSERT INTO pspayments_settings 
                (name, shop_id, api_key, api_secret_key, description, is_enable)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (settings.name, settings.shop_id, settings.api_key, settings.api_secret_key, settings.description))
            await conn.commit()

        return {
            "message": f"Настройки для {settings.name} успешно добавлены",
            "success": True,
            "name": settings.name,
            "shop_id": settings.shop_id
        }
    except Exception as e:
        logger.error(f"Ошибка при добавлении настроек PSPayments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/", response_model=Dict)
async def delete_pspayments_settings(
        settings: PSPaymentsSettingsDelete,
        db: Database = Depends(get_db)
):
    """
    Деактивация (удаление) настроек pspayments

    - **shop_id**: ID магазина pspayments для удаления
    """
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row

            cursor = await conn.execute(
                "SELECT name FROM pspayments_settings WHERE shop_id = ? AND is_enable = 1",
                (settings.shop_id,)
            )
            setting = await cursor.fetchone()

            if not setting:
                raise HTTPException(status_code=404, detail="Активные настройки с таким SHOP ID не найдены")

            await conn.execute(
                "UPDATE pspayments_settings SET is_enable = 0 WHERE shop_id = ?",
                (settings.shop_id,)
            )
            await conn.commit()

        return {
            "message": f"Настройки PSPayments для {setting['name']} успешно деактивированы",
            "success": True,
            "shop_id": settings.shop_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при деактивации настроек PSPayments: {e}")
        raise HTTPException(status_code=500, detail=str(e))