#!/usr/bin/env python3
"""Script to check user admin status in the database."""
import asyncio
from db import async_session
import repo
from config import settings

async def main():
    if not settings.ADMIN_IDS:
        print("⚠️  ADMIN_IDS not configured in .env file")
    else:
        print(f"📋 Configured ADMIN_IDS: {settings.ADMIN_IDS}")
    
    async with async_session() as session:
        # Get all users
        all_users = await repo.get_all_users(session)
        print(f"\n👥 Total users in DB: {len(all_users)}")
        
        for user in all_users:
            admin_status = "✅ ADMIN" if user.is_admin else "❌ Not admin"
            in_config = "🔧 In ADMIN_IDS" if user.tg_id in settings.ADMIN_IDS else ""
            print(f"  - ID: {user.id}, TG_ID: {user.tg_id}, Name: {user.full_name}, Admin: {admin_status} {in_config}")
        
        # Check specifically for ADMIN_IDS users
        print("\n🔍 Checking ADMIN_IDS users:")
        for admin_id in settings.ADMIN_IDS:
            user = await repo.get_user_by_tg_id(session, admin_id)
            if user:
                print(f"  - TG_ID {admin_id}: Found in DB, is_admin={user.is_admin}")
            else:
                print(f"  - TG_ID {admin_id}: ❌ NOT FOUND in DB")

if __name__ == "__main__":
    asyncio.run(main())
