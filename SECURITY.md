# Seguridad — transcriptor

Nivel **L2 (portfolio / repo público)** según la guía DevSecOps del paraguas. La app corre
solo en local, pero el repositorio es público, así que aplica los controles de publicación.

## Modelo de amenaza (breve)

- **Datos sensibles = el audio del usuario** (clases, reuniones, notas privadas) y sus
  transcripciones. El riesgo principal es **publicarlos por error**.
- La app no expone red (escucha solo en `127.0.0.1`), no maneja credenciales de terceros, no
  tiene usuarios ni base de datos. Superficie mínima.

## Controles

| Control | Cómo | Estado |
|---------|------|--------|
| **Datos del usuario fuera del repo** | `.gitignore` excluye `*.opus/*.mp3/*.m4a/*.wav`, `*.txt`, `audios/`, `salidas/`, `transcripciones/`. | ✅ |
| **Secretos fuera del repo** | `.env` gitignored; `.env.example` versiona solo las claves, sin valores. | ✅ |
| **Secret scanning en CI** | `gitleaks` escanea código e historial (`fetch-depth: 0`) y **bloquea** el build. | ✅ |
| **Lint** | `ruff` sobre el código propio. | ✅ |
| **Permisos mínimos en CI** | `permissions: contents: read`. | ✅ |
| **Sin escucha en red** | servidor atado a `127.0.0.1`. | ✅ |

## Contrato de secretos

La app **no requiere secretos** para funcionar. El `.env` solo lleva configuración no sensible
(modelo, puerto, carpeta de salida). Si en el futuro se agrega alguna integración con API key,
debe ir como variable de entorno y nunca versionarse.

## Política de remediación

Hallazgos de `gitleaks`/`ruff` se **remedian**, no se silencian. Si un hallazgo fuera un falso
positivo, se documenta la excepción con justificación y fecha de revisión (no se ignora de
forma permanente).
