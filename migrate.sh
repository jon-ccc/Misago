#!/bin/bash
# 同步数据库迁移
# 用法: ./migrate.sh

set -e

echo "==> 开始数据库迁移..."
docker compose exec misago python manage.py migrate
echo "==> 数据库迁移完成"
