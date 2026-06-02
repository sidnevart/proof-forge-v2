# Landing

Статический лендинг proof-forge — `index.html` + `demo.js` (Tailwind через CDN, без сборки).

## Локальный просмотр
```bash
open apps/landing/index.html
# или: python3 -m http.server -d apps/landing 8080
```

## Деплой на сервер
Монтируется в nginx-контейнер как `/var/www/proof-forge-landing/`, nginx отдаёт на корневом домене `proof-forge.ru`.
API остаётся на `api.proof-forge.ru` (не трогается).
