# Documentación del Proyecto

## Instalación
Para instalar este proyecto, necesitas ejecutar los siguientes comandos en tu terminal. Asegúrate de tener Node.js instalado en su versión más reciente.

```javascript
const express = require('express');
const app = express();

app.get('/api/users', (req, res) => {
    res.status(200).json({ message: "Obteniendo todos los usuarios activos del sistema" });
});

app.listen(3000, () => {
    console.log('Servidor corriendo en el puerto 3000');
});
```

```javascript
const express = require('express');
const app = express();

app.get('/api/users', (req, res) => {
    res.status(200).json({ message: "Obteniendo todos los usuarios activos del sistema" });
});

app.listen(3000, () => {
    console.log('Servidor corriendo en el puerto 3000');
});
```