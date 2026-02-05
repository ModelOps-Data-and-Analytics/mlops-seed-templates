# 📚 Datos para Knowledge Base - Ingesta

Este directorio contiene datos sintéticos para poblar la Knowledge Base del agente de Bedrock, junto con herramientas para subirlos a S3 e ingestarlos.

---

## 📁 Estructura

```
data/
├── README.md                     # Esta documentación
├── upload_kb_data.py             # Script para subir datos a S3
└── knowledge_base/               # Datos sintéticos
    ├── faqs.json                 # 15 Preguntas frecuentes
    ├── productos.json            # 8 Productos del catálogo
    ├── politicas.csv             # 15 Políticas de empresa
    ├── procedimientos.json       # 8 Guías paso a paso
    └── horarios_contacto.txt     # Horarios y contacto
```

---

## 📊 Contenido de los Datos

### `faqs.json` - Preguntas Frecuentes (15 registros)

| Categoría | Temas Cubiertos |
|-----------|-----------------|
| Envíos | Tiempo estándar, express, internacionales |
| Devoluciones | Política, reembolsos, costos |
| Pagos | Métodos aceptados, seguridad |
| Cuenta | Contraseña, actualización de datos |
| Productos | Garantía, disponibilidad |
| Pedidos | Seguimiento, modificaciones |

```json
{
  "id": "FAQ-001",
  "categoria": "Envíos",
  "pregunta": "¿Cuánto tiempo tarda el envío estándar?",
  "respuesta": "El envío estándar tarda entre 3 a 5 días hábiles..."
}
```

### `productos.json` - Catálogo de Productos (8 registros)

| SKU | Producto | Precio | Categoría |
|-----|----------|--------|-----------|
| TECH-001 | Widget Premium Pro | $89.990 | Tecnología |
| TECH-002 | Widget Lite | $49.990 | Tecnología |
| AUDIO-001 | SoundMax Auriculares | $34.990 | Audio |
| AUDIO-002 | BeatPods Earbuds | $24.990 | Audio |
| HOME-001 | SmartHub Centro Control | $59.990 | Hogar Inteligente |
| HOME-002 | SmartPlug Pack x3 | $19.990 | Hogar Inteligente |
| ACC-001 | PowerBank 20000mAh | $29.990 | Accesorios |
| ACC-002 | Funda Premium Widget Pro | $14.990 | Accesorios |

### `politicas.csv` - Políticas de Empresa (15 registros)

| ID | Categoría | Título |
|----|-----------|--------|
| POL-001 | Devoluciones | Política de Devolución Estándar |
| POL-002 | Devoluciones | Excepciones de Devolución |
| POL-003 | Devoluciones | Cambios de Talla |
| POL-004 | Garantía | Garantía Legal |
| POL-005 | Garantía | Garantía Extendida Electrónicos |
| POL-006 | Garantía | Garantía Electrodomésticos |
| POL-007 | Envíos | Envío Estándar Gratuito |
| POL-008 | Envíos | Envío Express |
| POL-009 | Envíos | Seguimiento de Envíos |
| POL-010 | Pagos | Métodos de Pago Aceptados |
| POL-011 | Pagos | Cuotas Sin Interés |
| POL-012 | Pagos | Facturación Empresas |
| POL-013 | Privacidad | Protección de Datos |
| POL-014 | Privacidad | Comunicaciones Marketing |
| POL-015 | Cuenta | Programa de Fidelidad |

### `procedimientos.json` - Guías Paso a Paso (8 registros)

| ID | Procedimiento |
|----|--------------|
| PROC-001 | Cómo realizar una compra |
| PROC-002 | Cómo cancelar un pedido |
| PROC-003 | Cómo solicitar una devolución |
| PROC-004 | Cómo hacer válida la garantía |
| PROC-005 | Cómo crear una cuenta |
| PROC-006 | Cómo usar un código de descuento |
| PROC-007 | Cómo contactar a soporte |
| PROC-008 | Cómo rastrear un envío |

### `horarios_contacto.txt` - Información de Contacto

- Horarios de atención por canal (chat, teléfono, WhatsApp, email)
- Tiendas físicas con direcciones y horarios
- Tiempos de respuesta garantizados
- Días festivos 2026
- Proceso de escalamiento de casos

---

## 🚀 Subir Datos a S3

### Requisitos Previos

```bash
# Instalar boto3 si no está instalado
pip install boto3

# Configurar credenciales AWS
aws configure
```

### Uso del Script

```bash
cd ml_pipelines/data

# Opción 1: Subir a bucket existente
python3 upload_kb_data.py \
  --bucket sagemaker-us-east-1-767397690934 \
  --prefix genai-bedrock-agent/knowledge-base-data/ \
  --region us-east-1

# Opción 2: Crear bucket nuevo y subir
python3 upload_kb_data.py \
  --bucket mi-nuevo-bucket-kb \
  --prefix knowledge-base-data/ \
  --create-bucket \
  --region us-east-1

# Opción 3: Ver archivos sin subir (dry run)
python3 upload_kb_data.py \
  --bucket mi-bucket \
  --dry-run
```

### Parámetros del Script

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--bucket` | Nombre del bucket S3 (requerido) | - |
| `--prefix` | Prefijo/carpeta en S3 | `knowledge-base-data/` |
| `--region` | Región AWS | `us-east-1` |
| `--create-bucket` | Crear bucket si no existe | `false` |
| `--dry-run` | Mostrar archivos sin subir | `false` |

### Output Esperado

```
============================================================
SUBIDA DE DATOS SINTÉTICOS A S3
============================================================
  Bucket: sagemaker-us-east-1-767397690934
  Prefix: genai-bedrock-agent/knowledge-base-data/
  Region: us-east-1
============================================================

Archivos encontrados (5):
  - faqs.json (6,116 bytes)
  - horarios_contacto.txt (3,361 bytes)
  - politicas.csv (5,334 bytes)
  - procedimientos.json (7,673 bytes)
  - productos.json (6,196 bytes)

Tamaño total: 28,680 bytes (28.0 KB)

Subiendo archivos...
✅ Subido: s3://bucket/prefix/faqs.json
✅ Subido: s3://bucket/prefix/horarios_contacto.txt
✅ Subido: s3://bucket/prefix/politicas.csv
✅ Subido: s3://bucket/prefix/procedimientos.json
✅ Subido: s3://bucket/prefix/productos.json

============================================================
RESUMEN
============================================================
  Archivos procesados: 5
  Subidos exitosamente: 5
  Errores: 0

  URI S3: s3://bucket/prefix/
============================================================
✅ Todos los archivos subidos correctamente
```

---

## 🔄 Ingesta en el Pipeline de SageMaker

### Flujo de Ingesta

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SUBIR DATOS A S3                                             │
│     upload_kb_data.py → s3://bucket/knowledge-base-data/         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. EJECUTAR PIPELINE                                            │
│     python run_pipeline.py --parameters                          │
│       KnowledgeBaseS3Uri=s3://bucket/knowledge-base-data/        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. STEP: CreateKnowledgeBase                                    │
│     - Crea KB con S3 Vectors                                     │
│     - Crea Data Source apuntando a S3                            │
│     - Ejecuta StartIngestionJob                                  │
│     - Espera a que termine la ingesta                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. OUTPUT: kb_output.json                                       │
│     {                                                            │
│       "knowledge_base_id": "KB-XXXXXXXX",                        │
│       "ingestion": {                                             │
│         "documents_indexed": 5,                                  │
│         "chunks_created": 85                                     │
│       }                                                          │
│     }                                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Ejecutar Pipeline con Ingesta

```bash
# Navegar al directorio del pipeline
cd ../

# Ejecutar con parámetros de ingesta
python3 run_pipeline.py \
  --pipeline-name BedrockAgentPipeline \
  --region us-east-1 \
  --parameters \
    KnowledgeBaseS3Uri=s3://sagemaker-us-east-1-767397690934/genai-bedrock-agent/knowledge-base-data/ \
    KBChunkMaxTokens=1024 \
    KBChunkOverlapPercentage=20 \
    KBIngestionTimeoutMinutes=30
```

### Parámetros de Ingesta del Pipeline

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `KnowledgeBaseS3Uri` | URI S3 con los documentos | - |
| `KBChunkMaxTokens` | Tamaño máximo de chunks | `1024` |
| `KBChunkOverlapPercentage` | Overlap entre chunks | `20` |
| `KBIngestionTimeoutMinutes` | Timeout de ingesta | `30` |
| `SkipKBIngestion` | Omitir ingesta | `false` |

---

## 📋 Formatos de Documentos Soportados

| Formato | Extensiones | Notas |
|---------|-------------|-------|
| **JSON** | `.json` | Estructuras anidadas soportadas |
| **CSV** | `.csv` | Cada fila como documento |
| **Texto** | `.txt`, `.md` | Texto plano |
| **PDF** | `.pdf` | Extrae texto (no imágenes) |
| **Word** | `.docx` | Office Open XML |
| **HTML** | `.html` | Extrae contenido sin tags |

---

## 📈 Métricas de Ingesta Esperadas

Para los 5 archivos de datos sintéticos (~28 KB):

| Métrica | Valor Esperado |
|---------|----------------|
| Documentos escaneados | 5 |
| Documentos indexados | 5 |
| Documentos fallidos | 0 |
| Chunks creados | 80-120 (depende del chunking) |
| Tiempo de ingesta | 2-5 minutos |

---

## 🔧 Agregar Más Datos

### Opción 1: Agregar archivos al directorio

1. Agrega archivos `.json`, `.csv`, `.txt` o `.md` a `knowledge_base/`
2. Ejecuta `upload_kb_data.py` nuevamente
3. Ejecuta el pipeline con el mismo `KnowledgeBaseS3Uri`
4. La ingesta actualizará chunks nuevos/modificados

### Opción 2: Actualizar datos existentes

1. Modifica los archivos en `knowledge_base/`
2. Ejecuta `upload_kb_data.py` (sobrescribe en S3)
3. Ejecuta el pipeline
4. La ingesta detectará cambios y actualizará vectores

### Ejemplo: Agregar nuevo FAQ

```json
// Agregar al array "documentos" en faqs.json
{
  "id": "FAQ-016",
  "categoria": "Promociones",
  "pregunta": "¿Tienen descuentos por temporada?",
  "respuesta": "Sí, realizamos ventas especiales en CyberDay, Black Friday, y Navidad con descuentos de hasta 50%."
}
```

---

## 🔗 URI S3 de Producción

```
s3://sagemaker-us-east-1-767397690934/genai-bedrock-agent/knowledge-base-data/
```

**Archivos disponibles:**
- `faqs.json` (6.0 KB)
- `horarios_contacto.txt` (3.3 KB)
- `politicas.csv` (5.2 KB)
- `procedimientos.json` (7.5 KB)
- `productos.json` (6.1 KB)

---

## 📞 Soporte

Para problemas con la ingesta:

1. Verificar credenciales AWS: `aws sts get-caller-identity`
2. Verificar acceso al bucket: `aws s3 ls s3://bucket/prefix/`
3. Revisar logs del pipeline en SageMaker Console
4. Verificar status de la Knowledge Base en Bedrock Console
