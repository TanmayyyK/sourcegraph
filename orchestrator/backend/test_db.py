import asyncio
from app.core.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT email, login_code, login_code_expires FROM users WHERE email='tanmaykumar3845@gmail.com'"))
        rows = result.fetchall()
        print(rows)

asyncio.run(main())
