# Revisión del dataset gold — Bloque G

> Documento de trabajo para la revisión humana (Javi). Para cada ejemplo se muestra pregunta, respuesta esperada, notas y el **contenido real del chunk gold** extraído de pgvector (SHA `40e33e4`), para verificar que la respuesta está fundamentada.

> **Cómo firmar:** revisa, ajusta lo que veas y marca el visto. Al confirmar, relleno `reviewed_by: javi` y `reviewed_at` en `gold.jsonl` y vuelvo a pasar validador + test.

**Total:** 40 ejemplos · 15 factual / 8 paráfrasis / 7 multi-fuente / 5 no sé / 5 multi-turno.

---

## Factual

### g-01 · Factual

**Pregunta:** ¿Qué comando de la FastAPI CLI arranca el servidor en modo desarrollo con auto-reload?

**Respuesta esperada:** El comando `fastapi dev`. Inicia el modo desarrollo y, por defecto, activa el auto-reload, que recarga el servidor automáticamente cuando cambias el código.

**Notas:** Factual directa sobre el comando de desarrollo. No confundir con `fastapi run` (producción).

**Chunks gold:**
- `fastapi-cli.md` → *FastAPI CLI > `fastapi dev`*
  > ## `fastapi dev`   Running `fastapi dev` initiates development mode.   By default, **auto-reload** is enabled, automatically reloading the server when you make changes to your code. This is resource-intensive and could be less stable than when it's disabled. You should only use it for development. It also listens on the IP address `127.0.0.1`, which is the IP for your machine to communicate with itself alone (`localhost`).

- [ ] Visto y aprobado

### g-02 · Factual

**Pregunta:** Si declaro un parámetro de ruta como `int`, ¿qué hace FastAPI con el valor recibido?

**Respuesta esperada:** Lo convierte (parsea) y valida como entero usando las anotaciones de tipo estándar de Python. Si el valor no es un entero válido, devuelve un error HTTP de validación.

**Notas:** Factual sobre parsing/validación de tipos en path params.

**Chunks gold:**
- `tutorial/path-params.md` → *Path Parameters > Path parameters with types*
  > ## Path parameters with types   You can declare the type of a path parameter in the function, using standard Python type annotations:   ```Python hl_lines="7" {!../../../docs_src/path_params/tutorial002.py!} ```   In this case, `item_id` is declared to be an `int`.   /// check   This will give you editor support inside of your function, with error checks, completion, etc.   ///

- [ ] Visto y aprobado

### g-03 · Factual

**Pregunta:** En el ejemplo de parámetros de consulta del tutorial, ¿qué valores por defecto tienen `skip` y `limit`?

**Respuesta esperada:** `skip` tiene valor por defecto `0` y `limit` tiene valor por defecto `10`.

**Notas:** Factual con valores concretos del ejemplo.

**Chunks gold:**
- `tutorial/query-params.md` → *Query Parameters > Defaults*
  > ## Defaults   As query parameters are not a fixed part of a path, they can be optional and can have default values.   In the example above they have default values of `skip=0` and `limit=10`.   So, going to the URL:   ``` http://127.0.0.1:8000/items/ ```   would be the same as going to:   ``` http://127.0.0.1:8000/items/?skip=0&limit=10 ```   But if you go to, for example:   ``` http://127.0.0.1:8000/items/?skip=20 ```   The parameter values in your function will be:   * `ski

- [ ] Visto y aprobado

### g-04 · Factual

**Pregunta:** ¿Cómo se declara un parámetro de consulta como opcional en FastAPI?

**Respuesta esperada:** Asignándole un valor por defecto de `None`. De esa forma el parámetro deja de ser obligatorio.

**Notas:** Factual sobre opcionalidad mediante default None.

**Chunks gold:**
- `tutorial/query-params.md` → *Query Parameters > Optional parameters*
  > ## Optional parameters   The same way, you can declare optional query parameters, by setting their default to `None`:   //// tab | Python 3.10+   ```Python hl_lines="7" {!> ../../../docs_src/query_params/tutorial002_py310.py!} ```   ////   //// tab | Python 3.8+   ```Python hl_lines="9" {!> ../../../docs_src/query_params/tutorial002.py!} ```   ////   In this case, the function parameter `q` will be optional, and will be `None` by default.   /// check   Also notice that **Fast

- [ ] Visto y aprobado

### g-05 · Factual

**Pregunta:** ¿Qué clase se usa en FastAPI para devolver respuestas HTTP de error al cliente?

**Respuesta esperada:** Se usa `HTTPException`. Se lanza con `raise HTTPException(...)` indicando el código de estado y el detalle del error.

**Notas:** Factual sobre el mecanismo de errores.

**Chunks gold:**
- `tutorial/handling-errors.md` → *Handling Errors > Use `HTTPException`*
  > ## Use `HTTPException`   To return HTTP responses with errors to the client you use `HTTPException`.

- [ ] Visto y aprobado

### g-06 · Factual

**Pregunta:** ¿De qué módulo procede originalmente la clase `BackgroundTasks`?

**Respuesta esperada:** Procede directamente de `starlette.background`. FastAPI la reexporta para que puedas importarla desde `fastapi`.

**Notas:** Factual sobre el origen de la clase (Starlette).

**Chunks gold:**
- `tutorial/background-tasks.md` → *Background Tasks > Technical Details*
  > ## Technical Details   The class `BackgroundTasks` comes directly from <a href="https://www.starlette.io/background/" class="external-link" target="_blank">`starlette.background`</a>.   It is imported/included directly into FastAPI so that you can import it from `fastapi` and avoid accidentally importing the alternative `BackgroundTask` (without the `s` at the end) from `starlette.background`.   By only using `BackgroundTasks` (and not `BackgroundTask`), it's then possible to

- [ ] Visto y aprobado

### g-07 · Factual

**Pregunta:** ¿Qué clase permite servir ficheros estáticos automáticamente desde un directorio?

**Respuesta esperada:** La clase `StaticFiles`. Se monta una instancia de `StaticFiles()` en una ruta concreta de la aplicación.

**Notas:** Factual sobre StaticFiles.

**Chunks gold:**
- `tutorial/static-files.md` → *Static Files*
  > # Static Files   You can serve static files automatically from a directory using `StaticFiles`.
- `tutorial/static-files.md` → *Static Files > Use `StaticFiles`*
  > ## Use `StaticFiles`   * Import `StaticFiles`. * "Mount" a `StaticFiles()` instance in a specific path.   ```Python hl_lines="2  6" {!../../../docs_src/static_files/tutorial001.py!} ```   /// note | "Technical Details"   You could also use `from starlette.staticfiles import StaticFiles`.   **FastAPI** provides the same `starlette.staticfiles` as `fastapi.staticfiles` just as a convenience for you, the developer. But it actually comes directly from Starlette.   ///

- [ ] Visto y aprobado

### g-08 · Factual

**Pregunta:** ¿Para qué sirve el parámetro `response_model` del decorador de la operación de ruta?

**Respuesta esperada:** Define el modelo de la respuesta y, sobre todo, garantiza que los datos privados se filtren. Con `response_model_exclude_unset` se devuelven solo los valores establecidos explícitamente.

**Notas:** Factual sobre el propósito de response_model.

**Chunks gold:**
- `tutorial/response-model.md` → *Response Model - Return Type > Recap*
  > ## Recap   Use the *path operation decorator's* parameter `response_model` to define response models and especially to ensure private data is filtered out.   Use `response_model_exclude_unset` to return only the values explicitly set.

- [ ] Visto y aprobado

### g-09 · Factual

**Pregunta:** ¿De qué clase hereda directamente `FastAPI`?

**Respuesta esperada:** `FastAPI` es una clase que hereda directamente de `Starlette`.

**Notas:** Factual; aparece en la nota de detalles técnicos del Step 1.

**Chunks gold:**
- `tutorial/first-steps.md` → *First Steps > Recap, step by step > Step 1: import `FastAPI`*
  > ## Recap, step by step   ### Step 1: import `FastAPI`   ```Python hl_lines="1" {!../../../docs_src/first_steps/tutorial001.py!} ```   `FastAPI` is a Python class that provides all the functionality for your API.   /// note | "Technical Details"   `FastAPI` is a class that inherits directly from `Starlette`.   You can use all the <a href="https://www.starlette.io/" class="external-link" target="_blank">Starlette</a> functionality with `FastAPI` too.   ///

- [ ] Visto y aprobado

### g-10 · Factual

**Pregunta:** ¿En qué dirección IP escucha por defecto `fastapi run`?

**Respuesta esperada:** Escucha en la IP `0.0.0.0`, lo que significa todas las direcciones IP disponibles, haciéndola accesible públicamente. Además, el auto-reload está desactivado por defecto.

**Notas:** Factual sobre el modo producción.

**Chunks gold:**
- `fastapi-cli.md` → *FastAPI CLI > `fastapi run`*
  > ## `fastapi run`   Executing `fastapi run` starts FastAPI in production mode by default.   By default, **auto-reload** is disabled. It also listens on the IP address `0.0.0.0`, which means all the available IP addresses, this way it will be publicly accessible to anyone that can communicate with the machine. This is how you would normally run it in production, for example, in a container.   In most cases you would (and should) have a "termination proxy" handling HTTPS for you

- [ ] Visto y aprobado

### g-11 · Factual

**Pregunta:** En el contexto de CORS, ¿por qué elementos está formado un "origin"?

**Respuesta esperada:** Un origin es la combinación de protocolo (`http`, `https`), dominio (p. ej. `myapp.com`, `localhost`) y puerto (p. ej. `80`, `443`, `8080`).

**Notas:** Factual sobre la definición de origin.

**Chunks gold:**
- `tutorial/cors.md` → *CORS (Cross-Origin Resource Sharing) > Origin*
  > ## Origin   An origin is the combination of protocol (`http`, `https`), domain (`myapp.com`, `localhost`, `localhost.tiangolo.com`), and port (`80`, `443`, `8080`).   So, all these are different origins:   * `http://localhost` * `https://localhost` * `http://localhost:8080`   Even if they are all in `localhost`, they use different protocols or ports, so, they are different "origins".

- [ ] Visto y aprobado

### g-12 · Factual

**Pregunta:** ¿Qué método del objeto de tareas en segundo plano se usa para registrar una tarea?

**Respuesta esperada:** El método `.add_task()`, al que se le pasa la función de tarea y sus argumentos.

**Notas:** Factual sobre .add_task().

**Chunks gold:**
- `tutorial/background-tasks.md` → *Background Tasks > Add the background task*
  > ## Add the background task   Inside of your *path operation function*, pass your task function to the *background tasks* object with the method `.add_task()`:   ```Python hl_lines="14" {!../../../docs_src/background_tasks/tutorial001.py!} ```   `.add_task()` receives as arguments:   * A task function to be run in the background (`write_notification`). * Any sequence of arguments that should be passed to the task function in order (`email`). * Any keyword arguments that should

- [ ] Visto y aprobado

### g-13 · Factual

**Pregunta:** ¿Qué biblioteca realiza la validación de datos por debajo en FastAPI?

**Respuesta esperada:** Toda la validación de datos la realiza Pydantic por debajo.

**Notas:** Factual sobre Pydantic como motor de validación.

**Chunks gold:**
- `tutorial/path-params.md` → *Path Parameters > Pydantic*
  > ## Pydantic   All the data validation is performed under the hood by <a href="https://docs.pydantic.dev/" class="external-link" target="_blank">Pydantic</a>, so you get all the benefits from it. And you know you are in good hands.   You can use the same type declarations with `str`, `float`, `bool` and many other complex data types.   Several of these are explored in the next chapters of the tutorial.

- [ ] Visto y aprobado

### g-14 · Factual

**Pregunta:** ¿Cómo se llama lo que devuelve una función definida con `async def`?

**Respuesta esperada:** Se llama "coroutine" (corrutina). Es el término técnico para lo que devuelve una función `async def`.

**Notas:** Factual sobre corrutinas.

**Chunks gold:**
- `async.md` → *Concurrency and async / await > Coroutines*
  > ## Coroutines   **Coroutine** is just the very fancy term for the thing returned by an `async def` function. Python knows that it is something like a function, that it can start and that it will end at some point, but that it might be paused ⏸ internally too, whenever there is an `await` inside of it.   But all this functionality of using asynchronous code with `async` and `await` is many times summarized as using "coroutines". It is comparable to the main key feature of Go, 

- [ ] Visto y aprobado

### g-15 · Factual

**Pregunta:** ¿Qué tipos de valores puede devolver una path operation function?

**Respuesta esperada:** Puede devolver un `dict`, una `list`, valores singulares como `str` o `int`, y también modelos de Pydantic, entre otros objetos.

**Notas:** Factual sobre tipos de retorno.

**Chunks gold:**
- `tutorial/first-steps.md` → *First Steps > Recap, step by step > Step 5: return the content*
  > ### Step 5: return the content   ```Python hl_lines="8" {!../../../docs_src/first_steps/tutorial001.py!} ```   You can return a `dict`, `list`, singular values as `str`, `int`, etc.   You can also return Pydantic models (you'll see more about that later).   There are many other objects and models that will be automatically converted to JSON (including ORMs, etc). Try using your favorite ones, it's highly probable that they are already supported.

- [ ] Visto y aprobado

---

## Paráfrasis

### g-16 · Paráfrasis

**Pregunta:** Mi función de endpoint hace una consulta a base de datos lenta pero no uso `await` en ningún sitio, la declaré con `def` normal. ¿Eso bloquea el servidor?

**Respuesta esperada:** No. Cuando declaras una path operation function con `def` normal en lugar de `async def`, FastAPI la ejecuta en un threadpool externo y luego la espera, en lugar de llamarla directamente, para que no bloquee el servidor.

**Notas:** Paráfrasis: el usuario describe el problema con sus palabras, no menciona 'threadpool'.

**Chunks gold:**
- `async.md` → *Concurrency and async / await > Very Technical Details > Path operation functions*
  > ### Path operation functions   When you declare a *path operation function* with normal `def` instead of `async def`, it is run in an external threadpool that is then awaited, instead of being called directly (as it would block the server).   If you are coming from another async framework that does not work in the way described above and you are used to defining trivial compute-only *path operation functions* with plain `def` for a tiny performance gain (about 100 nanoseconds

- [ ] Visto y aprobado

### g-17 · Paráfrasis

**Pregunta:** Tengo un modelo de usuario con la contraseña en texto plano y no quiero que se filtre cuando devuelvo el usuario por la API. ¿Cómo lo evito?

**Respuesta esperada:** Usa un modelo de salida distinto (sin el campo de contraseña) como `response_model`. FastAPI filtra los datos de la respuesta según ese modelo, de modo que la información privada no se expone.

**Notas:** Paráfrasis del caso clásico password in/out. No usa el término response_model en la pregunta.

**Chunks gold:**
- `tutorial/response-model.md` → *Response Model - Return Type > Return the same input data*
  > ## Return the same input data   Here we are declaring a `UserIn` model, it will contain a plaintext password:   //// tab | Python 3.10+   ```Python hl_lines="7  9" {!> ../../../docs_src/response_model/tutorial002_py310.py!} ```   ////   //// tab | Python 3.8+   ```Python hl_lines="9  11" {!> ../../../docs_src/response_model/tutorial002.py!} ```   ////   /// info   To use `EmailStr`, first install <a href="https://github.com/JoshData/python-email-validator" class="external-lin
- `tutorial/response-model.md` → *Response Model - Return Type > Recap*
  > ## Recap   Use the *path operation decorator's* parameter `response_model` to define response models and especially to ensure private data is filtered out.   Use `response_model_exclude_unset` to return only the values explicitly set.

- [ ] Visto y aprobado

### g-18 · Paráfrasis

**Pregunta:** Mi web en el navegador (puerto 8080) llama a mi API en otro puerto y el navegador bloquea las peticiones. ¿Qué tengo que configurar en FastAPI?

**Respuesta esperada:** Es un problema de CORS. Debes configurar `CORSMiddleware` en tu aplicación FastAPI: importarlo, crear una lista de orígenes permitidos y añadirlo como middleware, indicando además si permites credenciales, métodos y cabeceras.

**Notas:** Paráfrasis: describe el síntoma de CORS sin nombrarlo en términos técnicos.

**Chunks gold:**
- `tutorial/cors.md` → *CORS (Cross-Origin Resource Sharing) > Use `CORSMiddleware`*
  > ## Use `CORSMiddleware`   You can configure it in your **FastAPI** application using the `CORSMiddleware`.   * Import `CORSMiddleware`. * Create a list of allowed origins (as strings). * Add it as a "middleware" to your **FastAPI** application.   You can also specify whether your backend allows:   * Credentials (Authorization headers, Cookies, etc). * Specific HTTP methods (`POST`, `PUT`) or all of them with the wildcard `"*"`. * Specific HTTP headers or all of them with the 

- [ ] Visto y aprobado

### g-19 · Paráfrasis

**Pregunta:** ¿Tengo que instalar algo aparte para que aparezca el comando `fastapi` en mi terminal?

**Respuesta esperada:** No necesitas instalar nada aparte: al instalar FastAPI (por ejemplo con `pip install "fastapi[standard]"`) se incluye el paquete `fastapi-cli`, que proporciona el comando `fastapi` en la terminal.

**Notas:** Paráfrasis sobre la procedencia del comando fastapi.

**Chunks gold:**
- `fastapi-cli.md` → *FastAPI CLI*
  > # FastAPI CLI   **FastAPI CLI** is a command line program that you can use to serve your FastAPI app, manage your FastAPI project, and more.   When you install FastAPI (e.g. with `pip install "fastapi[standard]"`), it includes a package called `fastapi-cli`, this package provides the `fastapi` command in the terminal.   To run your FastAPI app for development, you can use the `fastapi dev` command:   <div class="termy">   ```console $ <font color="#4E9A06">fastapi</font> dev 

- [ ] Visto y aprobado

### g-20 · Paráfrasis

**Pregunta:** Quiero que un parámetro de la URL solo acepte un conjunto cerrado de valores válidos. ¿Cómo se hace?

**Respuesta esperada:** Usa un `Enum` estándar de Python como tipo del parámetro de ruta. Así los valores válidos quedan predefinidos.

**Notas:** Paráfrasis de 'predefined values' con Enum.

**Chunks gold:**
- `tutorial/path-params.md` → *Path Parameters > Predefined values*
  > ## Predefined values   If you have a *path operation* that receives a *path parameter*, but you want the possible valid *path parameter* values to be predefined, you can use a standard Python <abbr title="Enumeration">`Enum`</abbr>.

- [ ] Visto y aprobado

### g-21 · Paráfrasis

**Pregunta:** Trabajo en varios proyectos de Python a la vez y se me mezclan las librerías instaladas. ¿Qué recomienda la documentación?

**Respuesta esperada:** Usar un entorno virtual por cada proyecto. Un entorno virtual es un directorio donde instalas los paquetes de ese proyecto de forma aislada del entorno global, evitando que se mezclen entre proyectos.

**Notas:** Paráfrasis del problema de dependencias mezcladas.

**Chunks gold:**
- `virtual-environments.md` → *Virtual Environments > What are Virtual Environments*
  > ## What are Virtual Environments   The solution to the problems of having all the packages in the global environment is to use a **virtual environment for each project** you work on.   A virtual environment is a **directory**, very similar to the global one, where you can install the packages for a project.   This way, each project will have its own virtual environment (`.venv` directory) with its own packages.   ```mermaid flowchart TB subgraph stone-project[philosophers-sto

- [ ] Visto y aprobado

### g-22 · Paráfrasis

**Pregunta:** Leo un número desde una variable de entorno pero en Python me llega como cadena de texto. ¿Es lo esperado?

**Respuesta esperada:** Sí, es lo esperado. Las variables de entorno solo pueden manejar cadenas de texto, porque son externas a Python y deben ser compatibles con otros programas y sistemas operativos. Si necesitas otro tipo, tienes que convertir y validar el valor en Python.

**Notas:** Paráfrasis sobre que las env vars son siempre strings.

**Chunks gold:**
- `environment-variables.md` → *Environment Variables > Types and Validation*
  > ## Types and Validation   These environment variables can only handle **text strings**, as they are external to Python and have to be compatible with other programs and the rest of the system (and even with different operating systems, as Linux, Windows, macOS).   That means that **any value** read in Python from an environment variable **will be a `str`**, and any conversion to a different type or any validation has to be done in code.   You will learn more about using envir

- [ ] Visto y aprobado

### g-23 · Paráfrasis

**Pregunta:** ¿Cómo describo la estructura de los datos que mi API espera recibir en el cuerpo de la petición?

**Respuesta esperada:** Declarando un modelo de datos con Pydantic: importas `BaseModel` de `pydantic` y creas una clase que herede de `BaseModel` con los atributos y sus tipos.

**Notas:** Paráfrasis sobre declarar el request body con un modelo Pydantic.

**Chunks gold:**
- `tutorial/body.md` → *Request Body > Import Pydantic's `BaseModel`*
  > ## Import Pydantic's `BaseModel`   First, you need to import `BaseModel` from `pydantic`:   //// tab | Python 3.10+   ```Python hl_lines="2" {!> ../../../docs_src/body/tutorial001_py310.py!} ```   ////   //// tab | Python 3.8+   ```Python hl_lines="4" {!> ../../../docs_src/body/tutorial001.py!} ```   ////

- [ ] Visto y aprobado

---

## Multi-fuente

### g-24 · Multi-fuente

**Pregunta:** ¿Qué relación tienen FastAPI con Starlette y con Pydantic?

**Respuesta esperada:** FastAPI hereda directamente de Starlette (que aporta la parte web/ASGI) y usa Pydantic para toda la validación de datos. Es decir, se apoya en Starlette para el manejo HTTP y en Pydantic para validar y parsear los datos.

**Notas:** Multi-fuente: combina la herencia de Starlette (first-steps) con la validación de Pydantic (path-params).

**Chunks gold:**
- `tutorial/first-steps.md` → *First Steps > Recap, step by step > Step 1: import `FastAPI`*
  > ## Recap, step by step   ### Step 1: import `FastAPI`   ```Python hl_lines="1" {!../../../docs_src/first_steps/tutorial001.py!} ```   `FastAPI` is a Python class that provides all the functionality for your API.   /// note | "Technical Details"   `FastAPI` is a class that inherits directly from `Starlette`.   You can use all the <a href="https://www.starlette.io/" class="external-link" target="_blank">Starlette</a> functionality with `FastAPI` too.   ///
- `tutorial/path-params.md` → *Path Parameters > Pydantic*
  > ## Pydantic   All the data validation is performed under the hood by <a href="https://docs.pydantic.dev/" class="external-link" target="_blank">Pydantic</a>, so you get all the benefits from it. And you know you are in good hands.   You can use the same type declarations with `str`, `float`, `bool` and many other complex data types.   Several of these are explored in the next chapters of the tutorial.

- [ ] Visto y aprobado

### g-25 · Multi-fuente

**Pregunta:** Quiero servir una web estática y además permitir que su JavaScript llame a mi API desde otro origen. ¿Qué dos piezas de FastAPI necesito?

**Respuesta esperada:** Necesitas `StaticFiles` para servir los ficheros estáticos (montando una instancia en una ruta) y `CORSMiddleware` para permitir las llamadas cross-origin desde el navegador (configurando los orígenes permitidos).

**Notas:** Multi-fuente real: static-files + cors, ficheros distintos.

**Chunks gold:**
- `tutorial/static-files.md` → *Static Files > Use `StaticFiles`*
  > ## Use `StaticFiles`   * Import `StaticFiles`. * "Mount" a `StaticFiles()` instance in a specific path.   ```Python hl_lines="2  6" {!../../../docs_src/static_files/tutorial001.py!} ```   /// note | "Technical Details"   You could also use `from starlette.staticfiles import StaticFiles`.   **FastAPI** provides the same `starlette.staticfiles` as `fastapi.staticfiles` just as a convenience for you, the developer. But it actually comes directly from Starlette.   ///
- `tutorial/cors.md` → *CORS (Cross-Origin Resource Sharing) > Use `CORSMiddleware`*
  > ## Use `CORSMiddleware`   You can configure it in your **FastAPI** application using the `CORSMiddleware`.   * Import `CORSMiddleware`. * Create a list of allowed origins (as strings). * Add it as a "middleware" to your **FastAPI** application.   You can also specify whether your backend allows:   * Credentials (Authorization headers, Cookies, etc). * Specific HTTP methods (`POST`, `PUT`) or all of them with the wildcard `"*"`. * Specific HTTP headers or all of them with the 

- [ ] Visto y aprobado

### g-26 · Multi-fuente

**Pregunta:** ¿Cómo paso de las anotaciones de tipo de Python a obtener validación automática del cuerpo de la petición?

**Respuesta esperada:** FastAPI aprovecha las type hints de Python para soporte del editor, validación y conversión de datos. Para el cuerpo, declaras un modelo Pydantic (`BaseModel`) con atributos tipados, y FastAPI usa esas anotaciones para validar y parsear automáticamente la petición.

**Notas:** Multi-fuente: type hints (python-types) + request body con Pydantic (body).

**Chunks gold:**
- `python-types.md` → *Python Types Intro > Type hints in **FastAPI***
  > ## Type hints in **FastAPI**   **FastAPI** takes advantage of these type hints to do several things.   With **FastAPI** you declare parameters with type hints and you get:   * **Editor support**. * **Type checks**.   ...and **FastAPI** uses the same declarations to:   * **Define requirements**: from request path parameters, query parameters, headers, bodies, dependencies, etc. * **Convert data**: from the request to the required type. * **Validate data**: coming from each req
- `tutorial/body.md` → *Request Body > Import Pydantic's `BaseModel`*
  > ## Import Pydantic's `BaseModel`   First, you need to import `BaseModel` from `pydantic`:   //// tab | Python 3.10+   ```Python hl_lines="2" {!> ../../../docs_src/body/tutorial001_py310.py!} ```   ////   //// tab | Python 3.8+   ```Python hl_lines="4" {!> ../../../docs_src/body/tutorial001.py!} ```   ////

- [ ] Visto y aprobado

### g-27 · Multi-fuente

**Pregunta:** ¿Qué comando uso para desarrollar en local y cuál para producción, y en qué se diferencian?

**Respuesta esperada:** Para desarrollo usas `fastapi dev`, que activa el auto-reload por defecto y está pensado para iterar sobre el código. Para producción usas `fastapi run`, que desactiva el auto-reload y escucha en `0.0.0.0` para ser accesible públicamente.

**Notas:** Multi-fuente: requiere combinar las dos secciones (dev y run) para responder la diferencia.

**Chunks gold:**
- `fastapi-cli.md` → *FastAPI CLI > `fastapi dev`*
  > ## `fastapi dev`   Running `fastapi dev` initiates development mode.   By default, **auto-reload** is enabled, automatically reloading the server when you make changes to your code. This is resource-intensive and could be less stable than when it's disabled. You should only use it for development. It also listens on the IP address `127.0.0.1`, which is the IP for your machine to communicate with itself alone (`localhost`).
- `fastapi-cli.md` → *FastAPI CLI > `fastapi run`*
  > ## `fastapi run`   Executing `fastapi run` starts FastAPI in production mode by default.   By default, **auto-reload** is disabled. It also listens on the IP address `0.0.0.0`, which means all the available IP addresses, this way it will be publicly accessible to anyone that can communicate with the machine. This is how you would normally run it in production, for example, in a container.   In most cases you would (and should) have a "termination proxy" handling HTTPS for you

- [ ] Visto y aprobado

### g-28 · Multi-fuente

**Pregunta:** ¿Cuál es la diferencia entre un parámetro de ruta y un parámetro de consulta?

**Respuesta esperada:** Un parámetro de ruta forma parte del path de la URL (p. ej. `/items/{item_id}`) y se declara con la misma sintaxis de las format strings. Un parámetro de consulta es cualquier otro parámetro de la función que no está en el path; va después del `?` como pares clave-valor y puede tener valor por defecto y ser opcional.

**Notas:** Multi-fuente: contrasta path-params y query-params.

**Chunks gold:**
- `tutorial/path-params.md` → *Path Parameters*
  > # Path Parameters   You can declare path "parameters" or "variables" with the same syntax used by Python format strings:   ```Python hl_lines="6-7" {!../../../docs_src/path_params/tutorial001.py!} ```   The value of the path parameter `item_id` will be passed to your function as the argument `item_id`.   So, if you run this example and go to <a href="http://127.0.0.1:8000/items/foo" class="external-link" target="_blank">http://127.0.0.1:8000/items/foo</a>, you will see a resp
- `tutorial/query-params.md` → *Query Parameters*
  > # Query Parameters   When you declare other function parameters that are not part of the path parameters, they are automatically interpreted as "query" parameters.   ```Python hl_lines="9" {!../../../docs_src/query_params/tutorial001.py!} ```   The query is the set of key-value pairs that go after the `?` in a URL, separated by `&` characters.   For example, in the URL:   ``` http://127.0.0.1:8000/items/?skip=0&limit=10 ```   ...the query parameters are:   * `skip`: with a va

- [ ] Visto y aprobado

### g-29 · Multi-fuente

**Pregunta:** Mi aplicación crece. ¿Cómo la divido en varios ficheros y cómo escribo tests para ella?

**Respuesta esperada:** Para dividirla usas `APIRouter`, que funciona como un "mini FastAPI" donde declaras operaciones de ruta en módulos separados y luego las incluyes en la app principal. Para los tests usas `TestClient` (basado en httpx), creándolo con tu instancia `app` y escribiendo funciones de test estándar.

**Notas:** Multi-fuente: bigger-applications (APIRouter) + testing (TestClient).

**Chunks gold:**
- `tutorial/bigger-applications.md` → *Bigger Applications - Multiple Files > `APIRouter`*
  > ## `APIRouter`   Let's say the file dedicated to handling just users is the submodule at `/app/routers/users.py`.   You want to have the *path operations* related to your users separated from the rest of the code, to keep it organized.   But it's still part of the same **FastAPI** application/web API (it's part of the same "Python Package").   You can create the *path operations* for that module using `APIRouter`.
- `tutorial/testing.md` → *Testing > Using `TestClient`*
  > ## Using `TestClient`   /// info   To use `TestClient`, first install <a href="https://www.python-httpx.org" class="external-link" target="_blank">`httpx`</a>.   Make sure you create a [virtual environment](../virtual-environments.md){.internal-link target=_blank}, activate it, and then install it, for example:   ```console $ pip install httpx ```   ///   Import `TestClient`.   Create a `TestClient` by passing your **FastAPI** application to it.   Create functions with a name

- [ ] Visto y aprobado

### g-30 · Multi-fuente

**Pregunta:** ¿Cómo devuelvo un error HTTP al cliente y cómo le añado cabeceras personalizadas a ese error?

**Respuesta esperada:** Para devolver el error lanzas `HTTPException` con el código de estado y el detalle. Si además necesitas cabeceras personalizadas en el error, `HTTPException` admite un parámetro `headers` para añadirlas, algo útil en escenarios avanzados como ciertos mecanismos de seguridad.

**Notas:** Multi-fuente (dos secciones): uso básico + cabeceras personalizadas.

**Chunks gold:**
- `tutorial/handling-errors.md` → *Handling Errors > Use `HTTPException`*
  > ## Use `HTTPException`   To return HTTP responses with errors to the client you use `HTTPException`.
- `tutorial/handling-errors.md` → *Handling Errors > Add custom headers*
  > ## Add custom headers   There are some situations in where it's useful to be able to add custom headers to the HTTP error. For example, for some types of security.   You probably won't need to use it directly in your code.   But in case you needed it for an advanced scenario, you can add custom headers:   ```Python hl_lines="14" {!../../../docs_src/handling_errors/tutorial002.py!} ```

- [ ] Visto y aprobado

---

## No sé

### g-31 · No sé

**Pregunta:** ¿Cuánto cuesta el plan empresarial de FastAPI Cloud al mes?

**Respuesta esperada:** No tengo esa información en la documentación de FastAPI. No puedo darte un precio porque no aparece en el corpus disponible.

**Notas:** No sé: precios de un producto comercial que no está en las docs.

**Chunks gold:** _(ninguno — «no sé», se espera rechazo)_

- [ ] Visto y aprobado

### g-32 · No sé

**Pregunta:** ¿Cómo configuro Django REST Framework para conectarlo con PostgreSQL?

**Respuesta esperada:** No tengo esa información en la documentación de FastAPI. Esta documentación cubre FastAPI, no Django REST Framework.

**Notas:** No sé: pregunta sobre otro framework, fuera del corpus.

**Chunks gold:** _(ninguno — «no sé», se espera rechazo)_

- [ ] Visto y aprobado

### g-33 · No sé

**Pregunta:** ¿Cuántas personas trabajan a tiempo completo en el equipo que mantiene FastAPI?

**Respuesta esperada:** No tengo esa información en la documentación de FastAPI. El corpus no incluye datos sobre el tamaño del equipo.

**Notas:** No sé: dato organizativo no presente en el corpus.

**Chunks gold:** _(ninguno — «no sé», se espera rechazo)_

- [ ] Visto y aprobado

### g-34 · No sé

**Pregunta:** ¿Cuál es la capital de Australia?

**Respuesta esperada:** No tengo esa información en la documentación de FastAPI. Esa pregunta está fuera del ámbito de esta documentación.

**Notas:** No sé: pregunta de conocimiento general totalmente fuera de dominio.

**Chunks gold:** _(ninguno — «no sé», se espera rechazo)_

- [ ] Visto y aprobado

### g-35 · No sé

**Pregunta:** ¿Me recomiendas usar FastAPI o Express en tu opinión personal para mi proyecto?

**Respuesta esperada:** No tengo esa información en la documentación de FastAPI. No puedo dar una opinión personal; la documentación no compara FastAPI con Express en esos términos.

**Notas:** No sé: petición de opinión subjetiva, no respondible desde el corpus.

**Chunks gold:** _(ninguno — «no sé», se espera rechazo)_

- [ ] Visto y aprobado

---

## Multi-turno

### g-36 · Multi-turno

**Turnos previos:**
- 👤 ¿Qué son los parámetros de ruta en FastAPI?
- 🤖 Son variables que declaras en el path de la URL con la misma sintaxis de las format strings de Python, p. ej. `/items/{item_id}`; su valor se pasa como argumento a tu función.

**Pregunta:** ¿Y cómo le pongo un tipo a ese parámetro?

**Respuesta esperada:** Declaras el tipo del parámetro de ruta en la función con anotaciones de tipo estándar de Python, por ejemplo `item_id: int`. FastAPI lo validará y parseará según ese tipo.

**Notas:** Multi-turn: la pregunta depende del turno previo (path parameters).

**Chunks gold:**
- `tutorial/path-params.md` → *Path Parameters > Path parameters with types*
  > ## Path parameters with types   You can declare the type of a path parameter in the function, using standard Python type annotations:   ```Python hl_lines="7" {!../../../docs_src/path_params/tutorial002.py!} ```   In this case, `item_id` is declared to be an `int`.   /// check   This will give you editor support inside of your function, with error checks, completion, etc.   ///

- [ ] Visto y aprobado

### g-37 · Multi-turno

**Turnos previos:**
- 👤 ¿Qué son los parámetros de consulta (query parameters)?
- 🤖 Son los parámetros de la función que no forman parte del path; FastAPI los interpreta como query params, van tras el `?` en la URL como pares clave-valor y pueden tener valores por defecto.

**Pregunta:** ¿Y cómo hago que uno de ellos sea opcional?

**Respuesta esperada:** Le asignas un valor por defecto de `None`. Así ese parámetro de consulta deja de ser obligatorio.

**Notas:** Multi-turn: 'uno de ellos' se refiere a los query params del turno previo.

**Chunks gold:**
- `tutorial/query-params.md` → *Query Parameters > Optional parameters*
  > ## Optional parameters   The same way, you can declare optional query parameters, by setting their default to `None`:   //// tab | Python 3.10+   ```Python hl_lines="7" {!> ../../../docs_src/query_params/tutorial002_py310.py!} ```   ////   //// tab | Python 3.8+   ```Python hl_lines="9" {!> ../../../docs_src/query_params/tutorial002.py!} ```   ////   In this case, the function parameter `q` will be optional, and will be `None` by default.   /// check   Also notice that **Fast

- [ ] Visto y aprobado

### g-38 · Multi-turno

**Turnos previos:**
- 👤 ¿Para qué sirven las tareas en segundo plano (background tasks)?
- 🤖 Permiten ejecutar operaciones después de devolver la respuesta, útiles para cosas que no requieren que el cliente espere, como enviar notificaciones por email.

**Pregunta:** Vale, ¿y cómo añado una de esas tareas dentro de mi endpoint?

**Respuesta esperada:** Dentro de la path operation function, pasas tu función de tarea al objeto de tareas en segundo plano con el método `.add_task()`, indicando la función a ejecutar y sus argumentos.

**Notas:** Multi-turn: 'esas tareas' = background tasks del turno previo.

**Chunks gold:**
- `tutorial/background-tasks.md` → *Background Tasks > Add the background task*
  > ## Add the background task   Inside of your *path operation function*, pass your task function to the *background tasks* object with the method `.add_task()`:   ```Python hl_lines="14" {!../../../docs_src/background_tasks/tutorial001.py!} ```   `.add_task()` receives as arguments:   * A task function to be run in the background (`write_notification`). * Any sequence of arguments that should be passed to the task function in order (`email`). * Any keyword arguments that should

- [ ] Visto y aprobado

### g-39 · Multi-turno

**Turnos previos:**
- 👤 ¿Cómo devuelvo un error HTTP al cliente en FastAPI?
- 🤖 Lanzando `HTTPException` con `raise`, indicando el código de estado y el detalle del error.

**Pregunta:** ¿Y puedo añadirle cabeceras personalizadas a ese error?

**Respuesta esperada:** Sí. `HTTPException` admite un parámetro `headers` para añadir cabeceras personalizadas a la respuesta de error, algo útil en escenarios avanzados como ciertos casos de seguridad.

**Notas:** Multi-turn: 'ese error' = el HTTPException del turno previo.

**Chunks gold:**
- `tutorial/handling-errors.md` → *Handling Errors > Add custom headers*
  > ## Add custom headers   There are some situations in where it's useful to be able to add custom headers to the HTTP error. For example, for some types of security.   You probably won't need to use it directly in your code.   But in case you needed it for an advanced scenario, you can add custom headers:   ```Python hl_lines="14" {!../../../docs_src/handling_errors/tutorial002.py!} ```

- [ ] Visto y aprobado

### g-40 · Multi-turno

**Turnos previos:**
- 👤 ¿Cómo creo un entorno virtual para mi proyecto?
- 🤖 Creas el entorno virtual dentro del proyecto la primera vez que trabajas en él, por ejemplo con `python -m venv .venv` (o con `uv`).

**Pregunta:** Perfecto, ¿y cómo lo activo después de crearlo?

**Respuesta esperada:** Lo activas con el comando de activación correspondiente a tu sistema; en Linux/macOS es `source .venv/bin/activate`. Conviene hacerlo cada vez que abres una nueva sesión de terminal para trabajar en el proyecto.

**Notas:** Multi-turn: 'lo' = el entorno virtual creado en el turno previo.

**Chunks gold:**
- `virtual-environments.md` → *Virtual Environments > Activate the Virtual Environment*
  > ## Activate the Virtual Environment   Activate the new virtual environment so that any Python command you run or package you install uses it.   /// tip   Do this **every time** you start a **new terminal session** to work on the project.   ///   //// tab | Linux, macOS   <div class="termy">   ```console $ source .venv/bin/activate ```   </div>   ////   //// tab | Windows PowerShell   <div class="termy">   ```console $ .venv\Scripts\Activate.ps1 ```   </div>   ////   //// tab 

- [ ] Visto y aprobado
