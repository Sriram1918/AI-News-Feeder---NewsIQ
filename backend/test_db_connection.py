"""Test PostgreSQL connection"""
import asyncio
import asyncpg

async def test_connection():
    # Try with the credentials from .env
    credentials = [
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'newsapp',
            'password': 'newsapp_secure_password_123',
            'database': 'news_intelligence'
        },
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'newsapp_secure_password_123',
            'database': 'news_intelligence'
        },
    ]
    
    for cred in credentials:
        try:
            print(f"Trying user: {cred['user']}...")
            conn = await asyncpg.connect(**cred)
            version = await conn.fetchval('SELECT version()')
            print(f"[SUCCESS] PostgreSQL connection successful with user: {cred['user']}")
            print(f"  Version: {version[:70]}...")
            await conn.close()
            return True
        except Exception as e:
            print(f"[FAILED] User {cred['user']}: {str(e)[:80]}")
    
    print("\nAll connection attempts failed.")
    print("You may need to reset the Docker volume:")
    print("  docker-compose down -v")
    print("  docker-compose up -d")
    return False

if __name__ == '__main__':
    asyncio.run(test_connection())
