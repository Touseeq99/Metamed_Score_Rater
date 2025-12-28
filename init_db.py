import os
from database.database import engine, Base
from database.models import Base as ModelsBase

def init_db():
    print("Creating database tables...")
    # Create all tables
    ModelsBase.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
