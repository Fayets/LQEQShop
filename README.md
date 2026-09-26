# Lo que ellas quieren · by María Inés

Tienda online con la estructura de rameesamor.com.ar (Tiendanube, tema Rio) + panel para
cargar prendas y ver quién entra, qué mira y quién arma carrito. El pedido se cierra por
WhatsApp (sin pasarela), como en Coquetines.

## Correr

```bash
./run.sh
```

- Tienda: http://localhost:8030
- Panel: http://localhost:8030/admin

El PIN inicial sale de `LQEQ_ADMIN_PIN`. Sin esa variable arranca en `1234` y el panel
**obliga a cambiarlo** al primer ingreso (mínimo 6 caracteres).

## Estructura del backend

Igual que Coquetines: los **controladores** solo reciben el request y llaman a un
**servicio**; toda la lógica y el SQL viven en los servicios.

| Controlador (`app/controllers/`) | Servicio (`app/services/`) | Qué hace |
|---|---|---|
| `product_controller` | `product_services` | CRUD de prendas, talles/stock, colores, fotos, duplicar |
| `category_controller` | `category_services` | Categorías del menú |
| `order_controller` | `order_services` | Pedido desde la tienda + estados y stock desde el panel |
| `tracking_controller` | `tracking_services` | Eventos de navegación, carrito, newsletter |
| `metrics_controller` | `metrics_services` | Resumen, embudo, visitas, recorrido, suscriptoras |
| `slide_controller` | `slide_services` | Slider de portada, cuadros de categoría, logo |
| `settings_controller` | `settings_services` | Textos, contacto, colores |
| `store_controller` | `store_services` | Catálogo público y páginas HTML |
| `auth_controller` | `auth_services` | PIN, sesiones |

Además: `main.py` (arma la app), `config.py` (rutas y constantes), `schemas.py`
(cuerpos Pydantic), `deps.py` (`require_admin`, cookie, subida de archivos),
`db.py` (SQLite), `security.py` (hash del PIN, sesiones, límites), `images.py`
(normalización de fotos), `seed.py` (datos de muestra).

## Cómo funciona un pedido

1. La clienta elige color y talle, **Agregar al carrito**, completa nombre, WhatsApp,
   entrega y forma de pago, y toca **Enviar pedido por WhatsApp**.
2. El servidor recalcula los precios contra el catálogo (el navegador no manda precios),
   crea el pedido `LQ-0001` y abre WhatsApp con el detalle.
3. El pedido **no descuenta stock** al crearse: es una intención de compra.
4. En el panel, al pasarlo a **confirmado** o **entregado** se descuenta el stock; si vuelve
   a pendiente o se cancela, el stock vuelve.

## Qué mide

Cada navegador tiene un id al azar; con eso se une todo lo que hizo esa persona.

- **Resumen**: personas que entraron, carritos armados (y los que quedaron sin pedido),
  pedidos, ventas confirmadas, el embudo (entró → miró → carrito → empezó el pedido →
  pidió), de dónde vienen (Instagram, WhatsApp, Google…), celular vs. compu, día por día,
  prendas más miradas/pedidas y stock por agotarse.
- **Carritos que quedaron sin pedido** (en el Resumen): qué prendas dejó cada persona y de
  dónde vino. Tocando uno se ve su recorrido completo.

El origen sale de los `utm_source`, del referrer o del navegador interno de
Instagram/Facebook. Para links propios conviene agregar `?utm_source=instagram` (o
`whatsapp`, etc.).

## Datos de muestra

`python -m app.seed` carga 16 prendas, 3 fotos de portada y 2 cuadros con **fotos libres
de Unsplash** (`seed_img/`) para que la tienda no arranque vacía. Se reemplazan desde el
panel.

`python -m app.seed --demo-metrics` suma 140 visitas, carritos y pedidos inventados para
ver el panel con datos. El panel avisa mientras existan, y **Ajustes → Empezar a contar
de cero** los borra (incluidos los pedidos de demo).

## Publicar

`Dockerfile` + `docker-compose.yml` (escucha solo en 127.0.0.1:8030, para poner nginx o
Caddy adelante), `.env.example` y `deploy/backup.sh` (copia verificada de la base + fotos,
pensada para cron diario).
