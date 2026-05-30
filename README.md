# Sistema de Insumos al Mayor V2 Fix15 Railway

Primera versión local funcional.

## Incluye

- Login admin/comprador
- Productos editables
- Categorías editables
- Catálogo tipo e-commerce
- Búsqueda y panel de categorías
- Imagen desde WooCommerce
- Stock desde WooCommerce por SKU
- Precio unidad/docena/bulto
- Bulto configurable por producto
- Peso interno admin
- Carrito
- Generación de cotización PDF

## Importante

WooCommerce se usa solo para:
- stock
- imagen principal
- nombre web de referencia

Los precios se manejan dentro del sistema.

## Instalación

Coloca tu `.env` en la misma carpeta del archivo `.py`.

Instala dependencias:

```bash
py -m pip install -r requirements.txt
```

Ejecuta:

```bash
py -m streamlit run sistema_insumos_mayor_v1.py
```

## Usuario inicial

Usuario:

```text
colorinsumos@gmail.com
```

Contraseña:

```text
20880157
```

## Seguridad

No subas tu archivo `.env` a GitHub.


## Cambio Fix1

- Precio inteligente por cantidad:
  - 12 unidades aplican precio de docena automáticamente.
  - Cantidad igual o superior al bulto aplica precio de bulto.
  - Cantidades mixtas combinan bultos + docenas + unidades.


## Cambios V2 Comercial

- Menú ampliado estilo sistema de ventas:
  - Tienda
  - Carrito
  - Mis pedidos
  - Mis créditos
  - Dashboard
  - Productos
  - Categorías
  - Cotizaciones
  - Usuarios
  - Validar créditos
  - Reportes
  - Configuración
  - Respaldo

- Pedidos con PDF.
- Créditos con saldo, vencimiento y estado.
- Carga de pagos/comprobantes por el cliente.
- Validación de pagos por administrador.
- Estado de cuenta PDF.
- Reporte Excel.
- Respaldo manual y automático diario a carpeta local.

## Respaldo en Google Drive

Para respaldar en Drive, instala Google Drive para escritorio y usa una carpeta sincronizada como destino, por ejemplo:

```text
C:\Users\Rene\Google Drive\Backups\InsumosMayor
```

La app guardará allí archivos `.json` y copia `.db`.


## Cambios V2 Fix1

- El carrito ahora muestra claramente Contado / Crédito al procesar pedido.
- Si se elige Crédito, crea automáticamente la cuenta por cobrar.
- Respaldo ahora incluye:
  - Configuración de carpeta
  - Exportar manual a carpeta
  - Descargar respaldo JSON
  - Importar respaldo JSON
  - Modo fusionar o reemplazar


## Cambios V2 Fix2

- Corrige visual del carrito:
  - Ya no muestra 12 x precio promedio.
  - Muestra 12 unidades / precio aplicado: 1 docena / total correcto.
- Agrega botones + y - en el carrito.
- Permite editar cantidad directamente en el carrito.
- Agrega casilla de usuario ML / ENVÍO.
- El envío sugerido solo se calcula/carga si el usuario tiene ML / ENVÍO activo.


## Cambios V2 Fix3

- Fondo claro/light por defecto.
- En carrito, Contado / Crédito se elige antes de crear pedido, sin doble botón de procesar.
- Si el cliente no tiene ML / ENVÍO, no aparece campo de envío al procesar pedido.
- Usuarios ahora tienen listado, crear, editar, desactivar y eliminar seguro.
- Pedidos tienen cambio de estado y eliminación segura.
- Créditos tienen cambio de estado, eliminación de crédito y abonos.
- Abonos tienen validar, rechazar y eliminar.
- Categorías, productos y cotizaciones tienen eliminación administrativa.
- En tienda, el botón de ampliar ahora es una lupa compacta junto a la foto.


## Cambios V2 Fix4

- Si seleccionas Docena o Bulto en tienda, la cantidad queda bloqueada en 1 presentación.
- En carrito se especifica mejor:
  - 1 docena = 12 unidades
  - 1 bulto = X unidades
- En unidad sigue funcionando el precio inteligente:
  - 12 unidades aplican precio docena
  - cantidad de bulto aplica precio bulto
- Cotizaciones ahora tienen barra de búsqueda por:
  - número
  - cliente
  - RIF
  - fecha
  - estado
  - monto


## Cambios V2 Fix5

- Al eliminar la última cotización o pedido, el consecutivo retoma el número anterior.
- PDF de cotización/pedido corregido:
  - SKU limpio, sin `::docena` ni `::bulto`.
  - Columnas ajustadas para que Pres. no invada SKU.
  - Cant. ahora muestra:
    - número si son unidades sueltas
    - DOC si es 1 docena exacta
    - DOC x2, DOC x3 si son varias docenas exactas
    - BULTO o BULTO x2 si aplica
  - Pres. muestra las unidades equivalentes, por ejemplo 12 und o 50 und.


## Cambios V2 Fix6 POS

- Estados comerciales ampliados:
  - Pendiente de pago
  - Crédito / Pendiente de pago
  - Pago por validar
  - Confirmado
  - Procesado en POS
  - Finalizado / Pagado
  - Cancelado
  - Anulado
- Si un pedido se cancela, pasa a Cancelado y anula cualquier crédito asociado.
- Si un crédito se marca como Pagado, el pedido pasa a Finalizado / Pagado.
- Nuevo módulo: Control POS.
  - Pendientes por procesar en POS.
  - Procesados en POS.
  - Confirmación de que el pedido ya fue sacado del POS.
- Antes de crear pedido se reconsulta stock real en WooCommerce.
- PDF de pedido/cotización más limpio: elimina columna Pres.
- Cantidad del PDF queda como DOC, DOC x2, BULTO, BULTO x2 o 15 und.
- Cotización puede convertirse en pedido contado o crédito.
- Se mantiene tipo de usuario estándar y ML / ENVÍO.


## Cambios V2 Fix7

- En catálogo, el bulto ahora muestra:
  - precio unitario del bulto
  - total del bulto calculado según `bulto_contiene`
- Ejemplo:
  - Bulto: $1.80 c/u
  - Bulto Total (60 unidad): $108.00
- Bolívares ahora usan formato venezolano:
  - Bs. 1.224,00
  - Bs. 73.440,00
- La lógica de bulto ahora interpreta `precio_bulto` como precio unitario dentro del bulto.


## Cambios V2 Fix8

- La tienda/catálogo ahora usa encabezado compacto:
  - selector de categoría arriba
  - barra de búsqueda arriba
  - resumen del carrito arriba
  - botón Ver carrito arriba
- Se elimina la columna lateral para ganar espacio.
- Catálogo ahora muestra 4 columnas de productos en escritorio.
- Agregado botón rápido para actualizar stock WooCommerce desde tienda.


## Cambios V2 Fix9 Comercial

- Nuevo módulo Rentabilidad:
  - Costo proveedor unitario
  - Envío por bulto
  - Otros costos por bulto
  - Margen mínimo
  - Simulación de precios y costos
  - Margen por unidad, docena y bulto
  - Ganancia total por bulto

- Nuevo módulo Publicaciones:
  - Checklist Web, Instagram, MercadoLibre, Marketplace y WhatsApp
  - Links y notas por producto
  - Filtros por pendientes

- Nuevo módulo Vendedores:
  - Rol vendedor
  - Asignación de productos a vendedores
  - Lista lista para copiar y enviar por WhatsApp


## Cambios V2 Fix10

- Mejora visual y funcional de Vendedores / Asignaciones:
  - Panel del vendedor con métricas
  - Filtros por stock y publicaciones pendientes
  - Cards con imagen, stock, bultos, precios y pendientes
  - Quitar asignación desde el panel
  - Asignación con filtros
  - Texto para WhatsApp por tipo de lista
  - Descargar lista TXT

- Rentabilidad:
  - El % ahora se muestra como Margen objetivo.
  - La rentabilidad real se calcula automáticamente con precio de venta y costo real.
  - Se agregó precio sugerido para alcanzar el margen objetivo.
  - Puedes aplicar ese precio sugerido a unidad/docena/bulto.


## Cambios V2 Fix11

- Reportes ahora incluye pestaña Valor de inventario.
- Calcula valor total de inventario usando stock de WooCommerce y costos internos.
- Muestra:
  - valor inventario a costo
  - venta potencial a unidad
  - venta potencial a docena c/u
  - venta potencial a bulto c/u
  - ganancia estimada por escenario
- Permite sincronizar stock desde Reportes.
- Exporta inventario valorado en CSV.
- El reporte Excel incluye hoja “Inventario valorado”.


## Cambios V2 Fix12

- Usuarios:
  - Nueva sección “Examinar cliente”.
  - Muestra pedidos del usuario, total de dinero en pedidos, compras finalizadas y saldo de crédito.
  - Pestañas con pedidos, cotizaciones y créditos del usuario.
  - Reportes ahora incluye “Mejores clientes”.

- MercadoLibre:
  - Configuración agrega `% comisión MercadoLibre`.
  - Rentabilidad muestra sugerido MercadoLibre por unidad/docena/bulto.
  - Fórmula: precio divisas x tasa proveedor + % comisión MercadoLibre.
  - Nuevo rol `vendedor_mercadolibre`.
  - En tienda, admin y vendedor_mercadolibre ven el precio sugerido MercadoLibre.


## Cambios V2 Fix13

- Rentabilidad:
  - La búsqueda ahora filtra por nombre, SKU o categoría.
  - Muestra cuántos productos coinciden.
  - El selector despliega todas las coincidencias encontradas.
  - Agrega una vista expandible “Ver coincidencias encontradas”.


## Cambios V2 Fix14

- Rentabilidad:
  - Se eliminó el bloque “Ver coincidencias encontradas”.
  - Se agregó filtro por categoría.
  - La lista desplegable ahora muestra los productos filtrados por categoría y búsqueda.


## Cambios V2 Fix15 Railway

- Corrige error en Railway:
  - `TypeError: 'NoneType' object is not subscriptable`
- Si la sesión pierde `st.session_state.user`, vuelve al login en vez de romper.
- Incluye `Procfile`.
- Incluye `railway.json`.

Start command recomendado:

```bash
streamlit run sistema_insumos_mayor_v1.py --server.address=0.0.0.0 --server.port=$PORT
```
