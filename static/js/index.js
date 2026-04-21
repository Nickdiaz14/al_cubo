const html5QrCode = new Html5Qrcode("reader");
const overlay = document.getElementById('resultado-overlay');
let escaneando = true;

// --- RECARGAR DB ---
function recargarBaseDatos() {
    const btn = document.getElementById('btn-recargar');
    const textoOriginal = btn.innerText;
    btn.innerText = "⏳ Cargando...";
    btn.disabled = true;

    fetch('/recargar_db', { method: 'POST' })
    .then(response => response.json())
    .then(data => {
        alert(`✅ Datos actualizados.\nTotal usuarios en memoria: ${data.count}`);
        btn.innerText = textoOriginal;
        btn.disabled = false;
    })
    .catch(err => {
        alert("❌ Error al conectar con el servidor");
        btn.innerText = textoOriginal;
        btn.disabled = false;
    });
}

// --- SCANNER ---
const config = { fps: 10, qrbox: { width: 250, height: 250 } };

function onScanSuccess(decodedText, decodedResult) {
    if (!escaneando) return;
    escaneando = false;
    html5QrCode.pause();

    fetch('/validar_qr', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ qr_data: decodedText })
    })
    .then(response => response.json())
    .then(data => mostrarResultado(data))
    .catch(err => {
        console.error(err);
        alert("Error de conexión");
        reiniciarEscaneo();
    });
}

function mostrarResultado(data) {
    overlay.style.display = 'flex';
    // Importante: Limpiamos todas las clases de color anteriores
    overlay.classList.remove('success', 'error', 'warning', 'inactive');
    
    const icono = document.getElementById('icono');
    const titulo = document.getElementById('titulo-res');
    const nombre = document.getElementById('nombre-res');
    const doc = document.getElementById('doc-res');
    const extra = document.getElementById('extra-info');

    nombre.innerText = ''; doc.innerText = ''; extra.innerText = '';

    if (data.status === 'success') {
        overlay.classList.add('success');
        icono.className = 'fa-solid fa-square-check'; // Icono Check
        titulo.innerText = 'ACCESO PERMITIDO';
        nombre.innerText = 'Nombre: ' + data.nombre;
        doc.innerText = 'Doc: ' + data.documento;

    } else if (data.status === 'inactive') {
        overlay.classList.add('inactive');
        icono.className = 'fa-solid fa-user-slash'; // Icono Usuario Bloqueado
        titulo.innerText = 'ACCESO DENEGADO';
        nombre.innerText = 'Usuario: ' + data.nombre;
        doc.innerText = 'Doc: ' + data.documento;
        extra.innerText = 'ESTADO: USUARIO INACTIVO';

    } else if (data.status === 'used') {
        overlay.classList.add('warning');
        icono.className = 'fa-solid fa-circle-exclamation'; // Icono Alerta
        titulo.innerText = 'ACCESO DENEGADO';
        nombre.innerText = 'Usuario: ' + data.nombre;
        doc.innerText = 'Doc: ' + data.documento;
        extra.innerText = 'Este código ya fue utilizado';

    } else {
        overlay.classList.add('error');
        icono.className = 'fa-solid fa-circle-xmark'; // Icono X
        titulo.innerText = 'DENEGADO';
        extra.innerText = 'QR no registrado en el sistema';
    }
}

function reiniciarEscaneo() {
    overlay.style.display = 'none';
    escaneando = true;
    html5QrCode.resume();
}

Html5Qrcode.getCameras().then(devices => {
    if (devices && devices.length) {
        // Intenta usar la cámara trasera
        const cameraId = devices[devices.length - 1].id; 
        html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess);
    }
}).catch(err => {
    alert("Error iniciando cámara. Verifica HTTPS.");
});
