#!/bin/bash
H="Gosloto-Partner: bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0 Safari/537.36"
for p in $(seq 1 180); do
  f="pages/page_$p.json"
  [ -s "$f" ] && continue
  code=$(curl -s -o "$f" -w "%{http_code}" "https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive?game=6x45plus&count=100&page=$p" -H "$UA" -H "$H" --max-time 30)
  if [ "$code" != "200" ]; then echo "page $p -> $code"; sleep 2; fi
  sleep 0.25
done
echo DONE $(ls pages | wc -l)
