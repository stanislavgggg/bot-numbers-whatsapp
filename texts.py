"""All user-facing copy lives here. Edit freely (Spanish by default)."""

# Bump this whenever the disclaimer wording changes: it is stored with every lead as proof of what was accepted.
CONSENT_VERSION = "es-tg-v3"

CLUBS = {
    "rm": "Real Madrid",
    "fcb": "Barça",
    "atm": "Atlético de Madrid",
    "otro": "Otro equipo",
}

# {brand} = BRAND_NAME (who sends the messages), {privacy} = privacy link line (may be empty),
# {trust_extra} = optional extra trust lines from FREQUENCY_LINE / PROOF_LINE (may be empty).
# Copy mirrors the landing https://espack.lovable.app so what people accept matches what they get.
# Structure: hook -> what is inside -> what it looks like -> why it is safe -> consent -> legal line.
WELCOME = (
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
DONE = (
    "🎉 <b>¡Listo!</b> Tu pack llegará a <b>{phone}</b> por WhatsApp, de parte de <b>{brand}</b>.\n\n"
    "Cuando lo recibas, guarda el contacto para no perderte nada. Si cambias de idea: /borrar.\n\n"
    "18+ · Juega con responsabilidad."
)
ASK_CLUB = "⭐ <b>Opcional, 1 toque:</b> ¿de qué equipo eres? Así podemos enviarte pronósticos de tu equipo."
CLUB_THANKS = "✅ {club}. ¡Gracias!"
BTN_CHANNEL = "⚽ Ver canal"

DELETE_ASK = "¿Seguro que quieres borrar tus datos y darte de baja?"
BTN_DEL_YES = "🗑️ Sí, borrar"
BTN_DEL_NO = "Cancelar"
DELETED = "Hecho. Hemos borrado tus datos. Si cambias de idea, escribe /start."
NOTHING_TO_DELETE = "No tenemos datos tuyos guardados."
FALLBACK = "Escribe /start para empezar 👇"
