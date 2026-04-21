document.addEventListener('DOMContentLoaded', () => {
    const sellos = document.querySelectorAll('.passport-stamps-area img');
    const container = document.querySelector('.passport-stamps-area');
    const posicionesUsadas = []; 
    
    const RADIO_COLISION = 100;
    // Clave única de almacenamiento por pasaporte
    const STORAGE_KEY = `pasaporte_pos_${PASSPORT_CODE}`;
    
    // Cargar posiciones guardadas (si existen)
    let posicionesGuardadas = {};
    try {
        posicionesGuardadas = JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch(e) {
        posicionesGuardadas = {};
    }
    Object.values(posicionesGuardadas).forEach((sello) => {
        posicionesUsadas.push({ x: sello.x, y: sello.y });
    });
        
    const nuevosSellos = [];

    sellos.forEach((sello) => {
        const selloadId = sello.id; // ej: "sello_1"

        if (posicionesGuardadas[selloadId]) {
            // ✅ Sello ya existía → restaurar su posición guardada exacta
            const { x, y, rotate } = posicionesGuardadas[selloadId];
            sello.style.left = x + 'px';
            sello.style.top = y + 'px';
            sello.style.rotate = rotate;
            
            // Forzar que el sello antiguo aparezca estático sin animar
            sello.style.animation = 'none';
            sello.style.filter = 'none';
            sello.style.transform = 'scale(1) rotate(0deg)';
            sello.classList.add('active');
        } else {
            // 🆕 Sello nuevo → agrupar para procesar luego
            nuevosSellos.push({ sello, id: selloadId });
        }
    });

    setTimeout(() => {
    if (nuevosSellos.length > 0) {
        // Ejecutar los sellos nuevos después de "un segundito"
            nuevosSellos.forEach((item, index) => {
                const sello = item.sello;
                const selloadId = item.id;
                let x, y, rotate;
                let colision;
                let intentos = 0;
                const selloWidth = sello.clientWidth || 150; 
                const selloHeight = sello.clientHeight || 150;

                do {
                    colision = false;
                    x = Math.random() * (container.clientWidth - selloWidth);
                    y = Math.random() * (container.clientHeight - selloHeight);

                    for (let pos of posicionesUsadas) {
                        const dx = x - pos.x;
                        const dy = y - pos.y;
                        if (Math.sqrt(dx * dx + dy * dy) < RADIO_COLISION) {
                            colision = true;
                            break;
                        }
                    }
                    intentos++;
                } while (colision && intentos < 100);

                const signo = Math.random() > 0.5 ? "" : "-";
                rotate = `${signo}${(Math.random() * 190)}deg`;

                posicionesUsadas.push({ x, y });

                // Guardar esta nueva posición en localStorage
                posicionesGuardadas[selloadId] = { x, y, rotate };
                localStorage.setItem(STORAGE_KEY, JSON.stringify(posicionesGuardadas));

                // Aplicar estilos iniciales
                sello.style.left = x + 'px';
                sello.style.top = y + 'px';
                sello.style.rotate = rotate;

                // Animar aparición con slam secuencialmente (asegurando un tick del navegador)
                setTimeout(() => {
                    sello.classList.add('active');
                }, (index * 800) + 100);
            });
        }
    }, 2500); // Retraso de un segundo antes de que empiecen a aparecer los nuevos
});

// --- LÓGICA DEL ESCÁNER DE SELLOS ---
let html5QrCode = null;
const overlayScanner = document.getElementById('scanner-overlay');

function abrirEscaner() {
    overlayScanner.style.display = 'flex';
    if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("reader");
    }
    
    const config = { fps: 10, qrbox: { width: 250, height: 250 } };
    
    // Iniciar cámara trasera
    html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess)
    .catch(err => {
        alert("Error iniciando cámara. Verifica permisos o HTTPS.");
        cerrarEscaner();
    });
}

function cerrarEscaner() {
    overlayScanner.style.display = 'none';
    if (html5QrCode && html5QrCode.isScanning) {
        html5QrCode.stop().then(() => {
            console.log("Escáner detenido.");
        }).catch(err => console.error(err));
    }
}

function onScanSuccess(decodedText, decodedResult) {
    if (html5QrCode.isScanning) {
        html5QrCode.pause();
    }
    
    fetch('/registrar_sello', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            passport_code: PASSPORT_CODE,
            qr_sello: decodedText
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert("¡Sello agregado correctamente!");
            // Recargamos para reflejar el nuevo sello
            window.location.reload();
        } else {
            alert(`Error: ${data.message}`);
            html5QrCode.resume();
        }
    })
    .catch(err => {
        console.error(err);
        alert("Error de conexión");
        html5QrCode.resume();
    });
}
