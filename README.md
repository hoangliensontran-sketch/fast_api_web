docker compose build
docker compose up -d
docker compose exec web python /opt/scripts/init_db.py