#!/usr/bin/env python3
"""Script to manually grant admin rights to a user."""
import asyncio
import sys
from db import async_session
import repo

async def main():
    if len(sys.argv) != 2:
        print("Usage: python grant_admin.py <telegram_id>")
        print("Example: python grant_admin.py 707640458")
        return
    
    try:
        tg_id = int(sys.argv[1])
    except ValueError:
        print("❌ Invalid Telegram ID. Must be a number.")
        return
    
    async with async_session() as session:
        user = await repo.get_user_by_tg_id(session, tg_id)
        
        if user is None:
            print(f"❌ User with TG_ID {tg_id} not found in database.")
            print("   The user must first register via /start command.")
            return
        
        if user.is_admin:
            print(f"✅ User {user.full_name} (TG_ID: {tg_id}) is already an admin.")
            return
        
        await repo.update_user(session, tg_id, is_admin=True)
        print(f"✅ Granted admin rights to {user.full_name} (TG_ID: {tg_id})")

if __name__ == "__main__":
    asyncio.run(main())
