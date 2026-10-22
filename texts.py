"""All user-facing copy lives here. Edit freely (Spanish by default)."""

# Bump this whenever the disclaimer wording changes: it is stored with every lead as proof of what was accepted.
# DISCLAIMER=full is the long legal block (es-tg-v3); DISCLAIMER=short is one compact consent line (es-tg-v4-short).
CONSENT_VERSION = "es-tg-v3"
CONSENT_VERSION_SHORT = "es-tg-v4-short"


# Real data from the channel (Oct 2026). Override with env PROOF_LINE / RESULTS_LINE ("-" turns a line off).
# RESULTS_LINE changes every month: update it in the env, not in code.
DEFAULT_PROOF_LINE = "+2.800 aficionados en Telegram"
DEFAULT_RESULTS_LINE = "Octubre: 15 aciertos y 4 fallos publicados · balance +572 € (declarado por el canal, no auditado)"

# Separate paid-deposit offer. Shown only after the number is saved, and only when BONUS_URL is set.
BONUS_BLOCK = (
    "\n\n🎁 <b>Oferta aparte (con depósito, +18)</b>\n"
    "Bono de bienvenida CaptainsBet: <b>100% extra hasta 100 €</b> en tu primer depósito "
    "(solo nuevos usuarios, mínimo 5 €). Rollover x5, combinadas de 3+ selecciones, "
    "cuota 1,50-10,00, validez 3 días. Consulta las condiciones vigentes del operador.\n"
    '<a href="{url}">Consultar oferta en Telegram</a>\n'
    "El pack sigue siendo gratis: este bono es otra promoción y requiere registrarte y depositar."
)
BTN_VIEW_CHANNEL = "📊 Ver el canal y sus informes"


def consent_version(level: str) -> str:
    return CONSENT_VERSION if level == "full" else CONSENT_VERSION_SHORT


CLUBS = {
    "rm": "Real Madrid",
    "fcb": "Barça",
    "atm": "Atlético de Madrid",
    "otro": "Otro equipo",
}

# {brand} = BRAND_NAME (who sends the messages), {privacy} = privacy link (may be empty),
# {trust_extra} = optional extra lines from FREQUENCY_LINE / PROOF_LINE (may be empty).
# Offer first, consent last. SHORT keeps only what the "Acepto" tap needs to mean something: WhatsApp, sender, opt-out, 18+.
WELCOME_SHORT = (
    "⚽ <b>Pack de pronósticos. Gratis, en tu WhatsApp.</b>\n\n"
    "Qué apostar, a qué cuota y por qué. Fútbol con análisis, no solo un nombre de equipo:\n"
    "• <b>El pronóstico</b>: partido y apuesta propuesta.\n"
    "• <b>La cuota</b>: el precio de la apuesta, sin rodeos.\n"
    "• <b>El porqué</b>: las claves que justifican el pick.\n"
    "{trust_extra}\n"
    "✅ Gratis · sin tarjeta · sin depósito · sin cuenta\n\n"
    "<i>Al pulsar «Acepto» recibirás pronósticos y ofertas de {brand} por WhatsApp. "
    "Baja con /borrar. +18{privacy}</i>"
)

# Long legal version (DISCLAIMER=full). Copy mirrors the landing https://espack.lovable.app.
WELCOME_FULL = (
    "⚽ <b>Pack de pronósticos. Gratis, en tu WhatsApp.</b>\n\n"
    "Fútbol con análisis, no solo un nombre de equipo. En cada pack:\n"
    "• <b>El pronóstico</b>: partido y apuesta propuesta.\n"
    "• <b>La cuota</b>: el precio de la apuesta, sin rodeos.\n"
    "• <b>El porqué</b>: las claves que justifican el pick.\n\n"
    "<i>Así se ve (ejemplo ilustrativo, no es un pronóstico real):</i>\n"
    "<blockquote>⚽ Equipo A - Equipo B\n"
    "🎯 Más de 2,5 goles · cuota 1,85\n"
    "💡 Los dos suelen marcar en sus partidos recientes.</blockquote>\n\n"
    "✅ Gratis y sin compromiso: sin tarjeta, sin depósito y sin crear una cuenta.{trust_extra}\n\n"
    "📲 <b>Lo recibirás por WhatsApp.</b> Al pulsar «Acepto» y darnos tu número, aceptas recibir "
    "pronósticos y ofertas de {brand} por WhatsApp. Puedes darte de baja cuando quieras con /borrar.{privacy}\n\n"
    "18+ · Ningún pronóstico garantiza un resultado. Juega con responsabilidad. Solo para mayores de 18 años."
)
WELCOME = WELCOME_FULL  # backwards-compatible name
PRIVACY_INLINE = ' · <a href="{url}">Privacidad</a>'
PRIVACY_LINE = '\n<a href="{url}">Política de privacidad</a>'
BRAND_FALLBACK = "Apuestas Guru"

BTN_AGE_YES = "✅ Tengo 18+ y acepto · Quiero mi pack"
BTN_AGE_NO = "❌ No"
UNDERAGE = "Lo sentimos, este contenido es solo para mayores de 18 años. ¡Gracias por pasarte!"

ASK_PHONE = (
    "📲 <b>Solo falta tu número de WhatsApp.</b>\n\n"
    "Toca el botón de abajo si tu número de Telegram es el mismo que usas en WhatsApp. "
    "Si no, escríbelo sin el +34 (por ejemplo <code>612 345 678</code>).\n\n"
    "🔒 Lo usamos solo para escribirte por WhatsApp."
)
BTN_SHARE_PHONE = "📲 Usar mi número de Telegram"
BAD_PHONE = (
    "Ese número no parece válido 🤔\n"
    "Escríbelo con su prefijo si no es de España (por ejemplo <code>+34 612 345 678</code>)."
)
NOT_OWN_CONTACT = "Comparte tu propio número, por favor (o escríbelo a mano)."

# {brand} = who will write to the person on WhatsApp (so the first message is not a stranger).
DONE_SHORT = (
    "🎉 <b>¡Listo!</b> Tu pack llegará a <b>{phone}</b> por WhatsApp, de parte de <b>{brand}</b>.\n\n"
    "Cuando lo recibas, guarda el contacto para no perderte nada.{bonus}"
)
DONE_FULL = (
    "🎉 <b>¡Listo!</b> Tu pack llegará a <b>{phone}</b> por WhatsApp, de parte de <b>{brand}</b>.\n\n"
    "Cuando lo recibas, guarda el contacto para no perderte nada. Si cambias de idea: /borrar.\n\n"
    "18+ · Juega con responsabilidad.{bonus}"
)
DONE = DONE_FULL  # backwards-compatible name
ASK_CLUB = "⭐ <b>Opcional, 1 toque:</b> ¿de qué equipo eres? Así podemos enviarte pronósticos de tu equipo."
CLUB_THANKS = "✅ {club}. ¡Gracias!"
BTN_CHANNEL = "⚽ Ver canal"

DELETE_ASK = "¿Seguro que quieres borrar tus datos y darte de baja?"
BTN_DEL_YES = "🗑️ Sí, borrar"
BTN_DEL_NO = "Cancelar"
DELETED = "Hecho. Hemos borrado tus datos. Si cambias de idea, escribe /start."
NOTHING_TO_DELETE = "No tenemos datos tuyos guardados."
FALLBACK = "Escribe /start para empezar 👇"
