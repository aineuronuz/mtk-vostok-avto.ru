#!/bin/bash
# Каждый день: курс ЦБ и юаня на сегодня → цены под ключ на сайте → GitHub Pages (cron, 08:30 по серверу = 09:30 МСК)
set -e
cd /home/sergei/yurazol-sites/mtk-vostok-avto.ru
echo "== $(date '+%F %T')"
git pull -q --rebase
python3 new/site.py
git add -A docs/new new/data/rates.json new/data/last_build.json
if ! git diff --cached --quiet; then
  git -c user.name=aineuronuz -c user.email=aineuronuz@users.noreply.github.com commit -q -m "Цены под ключ на $(date +%d.%m.%Y)"
  git push -q
  echo "отправлено"
fi
