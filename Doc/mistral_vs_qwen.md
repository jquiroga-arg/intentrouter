# Informe: Mistral 7B Instruct vs Qwen3.5-9B para el ruteador de intenciones

> Contexto: clasificador de intenciones del chatbot municipal (San Isidro), prompt tipo `Promts/route_intent.txt`, inferencia vía Ollama.  
> Hardware de referencia: **NVIDIA L4, 24 GB VRAM** (~6 GB en uso con `qwen3.5:9b` en cuantización típica).  
> Fecha: 2026-04-17  
> Complementa: `analisis1.md` (problemas del prompt, taxonomía sugerida, JSON Schema, `think: false`, etc.).

---

## 1. Resumen ejecutivo

**No se recomienda sustituir Qwen3.5-9B por Mistral 7B Instruct** para esta tarea. Tener **VRAM libre** (p. ej. ~18 GB sin usar) no es un argumento a favor de un modelo **más pequeño**: habilita **mayor cuantización**, **más contexto efectivo** o un **modelo más grande**, no obliga a bajar a 7B.

La ganancia operativa esperada viene de **prompt + taxonomía + JSON Schema + evaluación con golden set** (como en `analisis1.md`), no de cambiar a Mistral 7B.

---

## 2. Por qué la VRAM libre no favorece a Mistral 7B

Los modelos de tamaño fijo **no “crecen”** al tener más VRAM disponible. El consumo depende de parámetros y cuantización, no del “espacio sobrante”.

| Opción con VRAM sobrante | Efecto |
|--------------------------|--------|
| Subir cuantización (Q4 → Q8 / FP16) | Mejora marginal de calidad en el **mismo** modelo |
| Aumentar `num_ctx` | Más tokens en ventana; depende del **límite del modelo** |
| Modelo más grande (p. ej. 12–14B) | Más capacidad para ambigüedades y reglas |
| Batching / concurrencia | Más throughput; independiente de “Mistral vs Qwen” |

**Mistral 7B Instruct** en Ollama suele rondar **~4 GB (Q4_K_M)** hasta **~7 GB (Q5)** o **~14 GB (FP16)** aproximadamente; no “usa mejor” 24 GB por ser más chico.

---

## 3. Comparativa orientada al caso de uso (español + JSON + municipio)

### 3.1. Idioma y dominio

- **Qwen3.5-9B**: fuerte en multilingüe (201 idiomas en ficha del modelo), adecuado para **español rioplatense**, voseo, typos y léxico municipal si se ancla en el prompt (vocabulario local en `analisis1.md`).
- **Mistral 7B Instruct**: entrenamiento mayoritariamente **inglés**; español **funcional** pero con más riesgo de errores en jerga, voseo y casos borde del golden set.

### 3.2. Salida JSON estricta

- Ambos pueden beneficiarse de **`format` (JSON Schema)** en Ollama.
- En la práctica, los modelos **más pequeños y “genéricos” en español** tienden a **prefijos, markdown o fences** si el prompt no es muy estricto. Qwen3.5 + Schema + opciones deterministas suele ser **más predecible** para un solo objeto JSON por turno.

### 3.3. Contexto largo (relevante para la Sugerencia 11 de `analisis1.md`)

- **Qwen3.5-9B**: ventana muy grande (**262K** en documentación / ficha citada en el análisis). Permite anexar **bancos grandes de FAQs o consultas etiquetadas** sin rediseñar el pipeline.
- **Mistral 7B Instruct** (familias v0.2 / v0.3 típicas): ventanas del orden de **8K–32K** según variante; **no** encaja igual de bien una estrategia “memoria en prompt” masiva.

### 3.4. Capacidad (parámetros) y ambigüedad

La taxonomía municipal tiene **solapamiento real** (salud vs trámites, deportes vs cultura, general vs trámites, etc., ver `analisis1.md` §2.3). Más parámetros suelen ayudar a **separar reglas de prioridad** sin tantas fallas en el borde. **9B > 7B** en expectativa para esa clase de discriminación fina.

### 3.5. “Thinking mode” (solo Qwen3.5)

- **Riesgo en Qwen3.5**: thinking activo por defecto puede inyectar bloques antes del JSON y romper el parser (prioridad alta en `analisis1.md` §2.2).
- **Mistral**: no tiene ese modo; es un **pro** operativo menor si **no** se mitiga Qwen.
- Mitigación recomendada (defensa en profundidad): API `think: false`, `/no_think` en prompt, parser que descarte thinking si aparece. Con eso, la ventaja de Mistral en este punto **se diluye**.

### 3.6. Licencia y despliegue

Ambas familias suelen ser **Apache 2.0** o equivalentes permisivos en variantes instruct comunes; no suele ser el factor decisivo frente a calidad en español y formato.

---

## 4. Tabla resumen

| Criterio | Qwen3.5-9B | Mistral 7B Instruct |
|----------|------------|----------------------|
| Español / voseo / local | Muy fuerte | Aceptable, más frágil |
| JSON + Schema Ollama | Muy alineado al flujo propuesto | Viable, más riesgo de “ruido” textual |
| Contexto masivo (FAQs en prompt) | Muy favorable | Limitado por ventana del modelo |
| Capacidad vs ambigüedad | Mejor | Peor |
| Thinking / latencia | Requiere mitigación explícita | Sin ese problema |
| VRAM típica (Q4) | ~6–7 GB (orden del análisis) | Menor; no implica mejor accuracy |
| Recomendación para **este** ruteador | **Base recomendada** | **No recomendado** como reemplazo |

---

## 5. Cómo aprovechar la L4 de 24 GB (sin cambiar a Mistral)

Orden sugerido de impacto / riesgo:

1. **Mantener Qwen3.5-9B** y aplicar `analisis1.md`: JSON Schema, `think: false`, taxonomía con prioridades, few-shot de bordes, `confidence` / `secondary_intent`.
2. **Subir cuantización** del mismo 9B (Q8 o FP16) si la latencia lo permite: mejora marginal con bajo riesgo de arquitectura.
3. **Probar un modelo más grande** en la misma GPU (p. ej. variantes **12–14B** de familias con buen español) **solo** si el golden set muestra techo claro en el 9B.
4. **Híbrido embeddings + kNN + LLM de respaldo** (ya alineado con `intentions` / embeddings en el análisis): gana latencia y coste por request; el LLM queda para baja confianza.

---

## 6. Conclusión

- **Mistral 7B Instruct no se espera que se comporte mejor** que Qwen3.5-9B para clasificación en español municipal con salida JSON estricta y posible contexto largo.
- La **VRAM libre** es argumento para **mejor inferencia del modelo elegido** (cuantización / concurrencia) o para **subir tamaño**, no para **reducir** parámetros sin necesidad.
- La prioridad de negocio sigue siendo **prompt + reglas + evaluación medible**, documentado en `analisis1.md`.

---

## 7. Referencias internas del repo

- `analisis1.md` — análisis del prompt, riesgos de thinking, Schema, taxonomía ampliada, configuración Ollama.
- `Promts/route_intent.txt` / `Promts/route_intent2.txt` — versiones del clasificador.
