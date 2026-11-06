#!/bin/bash
H="Gosloto-Partner: bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0 Safari/537.36"
for p in $(seq 1 390); do
  f="pages6x45/page_$p.json"
  [ -s "$f" ] && continue
  for a in 1 2 3 4; do
    code=$(curl -s -o "$f" -w "%{http_code}" "https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive?game=6x45&count=100&page=$p" -H "$UA" -H "$H" --max-time 30)
    [ "$code" = "200" ] && break
    sleep 2
  done
  [ "$code" != "200" ] && { echo "FAIL page $p ($code)"; rm -f "$f"; exit 1; }
  sleep 0.2
done
echo DONE $(ls pages6x45 | wc -l)
