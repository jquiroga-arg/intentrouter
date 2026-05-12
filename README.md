# Ruteador Inten — Chat en consola con Semantic Router + Ollama

Proyecto de demostración que clasifica la intención del usuario con **[semantic-router](https://github.com/aurelio-labs/semantic-router)** (embeddings locales con Hugging Face) y genera la respuesta con **Ollama** y un modelo tipo **Qwen 3.5 9B**. Las rutas del router se generan en tiempo de arranque a partir del CSV de intenciones.

**Entorno por defecto:** Windows con **GPU NVIDIA** y **CUDA** para el encoder PyTorch (`semantic_router.encoder.device`: `"cuda"`). El chat con Ollama usa la GPU que Ollama asigne según su propia configuración y drivers.

## Arquitectura

```mermaid
flowchart TB
    subgraph consola["Consola del usuario"]
        U[Entrada de texto]
    end

    subgraph app["ruteador_semantico"]
        CFG[config.json / RUTEADOR_CONFIG]
        CSV[Test/intents.csv]
        PROMPT["Prompts/router.txt\n(clasificador LLM)"]
        LD[routes_csv.py]
        MAIN[main.py]
        CFG --> MAIN
        CSV --> LD
        LD -->|Route por categoría| MAIN
        PROMPT -.->|"si llm_fallback=true"| MAIN
    end

    subgraph sr["semantic-router"]
        ENC[HuggingFaceEncoder + PyTorch CUDA]
        IDX[Índice local auto_sync]
        SR[SemanticRouter]
        LLM_WRAPPER[ConfigurableOllamaLLM]
        ENC --> SR
        IDX --> SR
        LLM_WRAPPER --> SR
    end

    subgraph ollama_svc["Ollama /api/chat  —  think:false"]
        MODEL["Modelo ej. qwen3.5:9b"]
    end

    U --> MAIN
    MAIN -->|utterance| SR
    SR -->|"RouteChoice.name"| MAIN
    SR -. "null → fallback LLM" .-> MAIN
    MAIN -->|"think:false + JSON Schema\n(clasificador)"| ollama_svc
    MAIN -->|"think:false + system_prompt\n(respuesta)"| ollama_svc
    ollama_svc -->|respuesta| MAIN
    MAIN --> U
```

Flujo resumido:

1. Al iniciar, se lee `config.json`, se resuelve la ruta del CSV y se construyen objetos `Route` (una ruta por categoría, con todas las frases de ejemplo de esa categoría).
2. **SemanticRouter** codifica la consulta con el encoder y decide la intención por similitud semántica.
3. Si ninguna ruta supera el umbral de similitud y `llm_fallback` está activo, se hace un segundo pase con `Prompts/router.txt` como system prompt y schema JSON estricto (`INTENT_JSON_SCHEMA`) para obtener la intención.
4. El mismo modelo Ollama recibe un **system prompt** que incluye la intención detectada y responde al usuario en lenguaje natural.

Todos los llamados a Ollama usan `"think": false` (HTTP, nivel raíz del payload) para suprimir los bloques `<think>…</think>` de Qwen3.5, y reintentan automáticamente con backoff exponencial ante fallas transitorias.

## Estructura del repositorio

| Ruta | Descripción |
|------|-------------|
| `config.json` | Configuración por entorno (modelo, Ollama, CSV, prompts, **device CUDA** del encoder). |
| `requirements.txt` | Dependencias Python; **PyTorch con wheels CUDA 12.4** para Windows + NVIDIA. |
| `requirements-dev.txt` | Dependencias de desarrollo: `pytest`. |
| `install-windows-cuda.ps1` | Script de PowerShell: venv + `pip install -r requirements.txt` + comprobación `torch.cuda`. |
| `conftest.py` | Configuración raíz de pytest (agrega el proyecto al path). |
| `ruteador_semantico/` | Código de la aplicación. |
| `ruteador_semantico/main.py` | Arranque, logging, bucle de chat, fallback LLM. |
| `ruteador_semantico/routes_csv.py` | Generación de `Route` desde el CSV. |
| `ruteador_semantico/ollama_llm.py` | LLM compatible con semantic-router, host configurable, retry y JSON Schema. |
| `ruteador_semantico/load_config.py` | Carga de JSON y resolución de rutas relativas. |
| `Test/intents.csv` | Dataset de ejemplo: `id,utterance,category` (sin fila de cabecera). |
| `Prompts/router.txt` | System prompt del clasificador LLM de fallback (9 categorías, `/no_think`, JSON Schema). |
| `tests/` | Tests unitarios (pytest). |
| `tests/test_routes_csv.py` | 13 casos: parsing CSV, BOM, acentos, CSV real de producción. |
| `tests/test_load_config.py` | 12 casos: carga de config, BOM, `resolve_path`, variable de entorno. |
| `tests/conftest.py` | Mock de `semantic_router`/`pydantic`/`ollama` para CI sin GPU ni dependencias pesadas. |
| `Doc/` | Notas de contexto (análisis del prompt, comparativa de modelos, referencia de semantic-router). |

## Dependencias

### Declaradas en `requirements.txt`

| Paquete | Uso |
|---------|-----|
| `torch` (wheel **cu124**) | Backend GPU del encoder vía `--extra-index-url` de PyTorch; evita el wheel solo-CPU por defecto en PyPI. |
| `semantic-router[local]` | Router semántico + encoder Hugging Face local (`transformers`, etc.). |
| `ollama` | Cliente Python para el `pull` del modelo al arrancar. |
| `requests` | Peticiones HTTP directas a `/api/chat` (clasificador y respuesta); permite pasar `think:false` al nivel raíz del payload. |

### Transitivas relevantes

**transformers**, **tokenizers**, etc. La primera ejecución descarga el modelo de embeddings (`semantic_router.encoder.name`, por defecto `sentence-transformers/all-MiniLM-L6-v2`).

**llama-cpp-python** (traído por `semantic-router[local]`): si pip no encuentra un wheel precompilado para tu versión de Python y Windows, intentará **compilar** el paquete; en ese caso hacen falta las herramientas C++ del apartado siguiente.

### Requisitos del sistema (Windows + CUDA)

- **Windows 10/11** (64 bits).
- **Python** 3.10 u 11 recomendado (64 bits, desde [python.org](https://www.python.org/downloads/windows/)).
- **GPU NVIDIA** con drivers recientes; comprobar con `nvidia-smi` en PowerShell.
- **CUDA 12.x** compatible con el wheel usado: el repo apunta a **CUDA 12.4** (`cu124`) en el índice de PyTorch. Si tu driver/stack usa otra variante, cambia la línea `--extra-index-url` en `requirements.txt` según la [matriz oficial de PyTorch](https://pytorch.org/get-started/locally/).
- **[Ollama para Windows](https://ollama.com/download)** con el modelo de `router_model.name`. Ollama usa la GPU NVIDIA automáticamente cuando los drivers lo permiten (comprueba con `nvidia-smi` mientras generas texto).
- **Compilación C++ (recomendado para `pip install`):** instala [Build Tools para Visual Studio](https://visualstudio.microsoft.com/es/visual-cpp-build-tools/) (o Visual Studio completo) con la carga de trabajo **Desarrollo de escritorio con C++** (MSVC, Windows SDK, entorno para `nmake`). Así evitas errores del tipo *`nmake` no encontrado* o *`CMAKE_C_COMPILER not set`* al construir **llama-cpp-python**. Tras instalarlo, ejecuta la instalación de dependencias desde **PowerShell para desarrolladores de VS** o **Símbolo del sistema de herramientas nativas x64**, o asegúrate de que el PATH incluya el kit de compilación, para que CMake encuentre el compilador.

## Instalación (Windows + NVIDIA CUDA)

1. Clonar o copiar el repositorio y abrir **PowerShell** en la raíz del proyecto (si compilaste dependencias nativas, usa **PowerShell para desarrolladores** según el requisito anterior).

2. Instalación asistida (recomendado): crea `.venv`, instala dependencias y verifica `torch.cuda.is_available()`:

   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
   .\install-windows-cuda.ps1
   .\.venv\Scripts\Activate.ps1
   ```

3. **Instalación manual** (equivalente al script):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
   ```

4. Instalar y arrancar **Ollama**. Comprobar API en `ollama.host` del `config.json` (por defecto `http://127.0.0.1:11434`).

5. Descargar el modelo de chat:

   ```powershell
   ollama pull qwen3.5:9b
   ```

   El nombre debe coincidir con `router_model.name` en `config.json`.

### Solo CPU en este mismo repo

Si necesitas ejecutar sin GPU, en `config.json` pon `"device": "cpu"` bajo `semantic_router.encoder` y sustituye `requirements.txt` por una instalación estándar sin `--extra-index-url` (por ejemplo solo `pip install torch --index-url https://download.pytorch.org/whl/cpu` más el resto de paquetes), o instala `torch` CPU desde la documentación de PyTorch.

## Configuración (`config.json`)

Todas las variables que suelen cambiar entre entornos conviven en un solo archivo en la raíz. Las rutas relativas (p. ej. `intents_csv`) se resuelven **respecto al directorio donde está el `config.json`**. Los archivos con BOM UTF-8 (común al guardar desde Excel o Notepad en Windows) se leen correctamente.

| Clave | Descripción |
|-------|-------------|
| `branch` | Etiqueta de rama o despliegue (solo metadato; se muestra al listar rutas). |
| `environment` | Nombre del entorno (por defecto `windows-cuda`). |
| `intents_csv` | Ruta al CSV de intenciones (relativa al `config.json` o absoluta). |
| `ollama.host` | URL base del API de Ollama (sin barra final recomendable). |
| `ollama.pull_on_startup` | Si es `true`, intenta `pull` del modelo al arrancar. |
| `ollama.chat_timeout_seconds` | Timeout HTTP para cada llamada a Ollama. |
| `ollama.max_retries` | Número de reintentos con backoff exponencial (1 s / 2 s / 4 s…) ante fallas de red o 5xx. Por defecto `3`. |
| `router_model.name` | Nombre del modelo en Ollama (clasificador y respuesta). |
| `router_model.temperature` | Temperatura de generación (default `0.1`; menor = respuestas más deterministas). |
| `router_model.max_tokens` | Límite de tokens generados (`num_predict` en Ollama). |
| `semantic_router.encoder.name` | Modelo Hugging Face para embeddings. |
| `semantic_router.encoder.device` | Por defecto **`"cuda"`** (GPU NVIDIA). Usa `"cpu"` si no hay CUDA o para depuración. |
| `semantic_router.encoder.score_threshold` | Umbral mínimo de similitud; consultas por debajo disparan el fallback LLM si está activo. |
| `semantic_router.auto_sync` | Modo de índice local (p. ej. `"local"`). |
| `semantic_router.top_k` | Top-K del router. |
| `semantic_router.aggregation` | Estrategia de agregación (p. ej. `"mean"`). |
| `semantic_router.llm_fallback` | `true` activa el clasificador LLM cuando el encoder no supera el umbral. Por defecto `false`. |
| `semantic_router.classifier_prompt_file` | Ruta al system prompt del clasificador LLM de fallback (p. ej. `"Prompts/router.txt"`). Solo se usa si `llm_fallback` es `true`. |
| `chat.system_prompt` | Prompt de sistema para la respuesta al usuario; debe incluir el placeholder `{route_name}`. |
| `chat.exit_commands` | Palabras para salir del bucle (comparación sin distinguir mayúsculas). |

### Otro archivo de configuración

- Variable de entorno **`RUTEADOR_CONFIG`**: ruta absoluta o relativa a otro `config.json`.
- Línea de comandos: `python -m ruteador_semantico --config ruta\al\config.json`.

## Formato del CSV de intenciones

- **Sin fila de cabecera.**
- Columnas: `id`, `utterance`, `category` (separador coma; la frase puede ir entre comillas si lleva comas).
- Se agrupan todas las filas por `category` y cada categoría se convierte en una **`Route`** con `name = category` y `utterances` = lista de frases no vacías.

## Ejecución

Desde la raíz del proyecto (donde existe la carpeta `ruteador_semantico`):

```powershell
python -m ruteador_semantico
```

Con configuración explícita:

```powershell
python -m ruteador_semantico --config "D:\Dev\Ruteador Inten\config.json"
```

Al arrancar, los mensajes de diagnóstico (ruta del config, estado CUDA, descarga del modelo) se emiten por **stderr** mediante el módulo `logging`. El nivel de detalle se controla con la variable de entorno `RUTEADOR_LOG_LEVEL` (valores: `DEBUG`, `INFO`, `WARNING`, `ERROR`; por defecto `INFO`):

```powershell
$env:RUTEADOR_LOG_LEVEL = "DEBUG"
python -m ruteador_semantico
```

Luego se imprime en **stdout** el **listado de rutas** con sus ejemplos y arranca el chat interactivo: escribís mensajes, el programa muestra la intención detectada y la respuesta del modelo. Para salir, usá una de las cadenas en `chat.exit_commands` (p. ej. `salir`).

### Tests unitarios

```powershell
pip install -r requirements-dev.txt
pytest tests/ -v
```

Los tests en `tests/` no requieren GPU ni Ollama en ejecución: `tests/conftest.py` reemplaza las dependencias pesadas (`semantic_router`, `pydantic`, `ollama`) con mocks livianos para que el CI funcione en cualquier entorno.

## Documentación adicional

- `Doc/semanticRouter.md` — referencia rápida de semantic-router con Ollama.
- `Doc/analisis_prompt.md` — análisis del prompt clasificador, taxonomía de categorías, recomendaciones.
- `Doc/mistral_vs_qwen.md` — comparativa de modelos para el caso de uso municipal.
- Repositorio upstream: [aurelio-labs/semantic-router](https://github.com/aurelio-labs/semantic-router).

## Nota sobre los llamados HTTP a Ollama

Todos los llamados a `/api/chat` se hacen con `requests.post()` directamente (no con `ollama.Client.chat()`). Esto permite pasar `"think": false` al nivel raíz del payload de Ollama, parámetro necesario para suprimir el modo *thinking* de Qwen3.5 y recibir respuestas limpias. La URL base se lee siempre de `ollama.host` en `config.json`. Si Ollama corre en otra máquina o en Docker, ajustá ese valor y la conectividad de red en consecuencia.
