# Email-to-SMS gateways for Canadian carriers.
#
# NOTE: carriers have been retiring these gateways (Rogers/Fido delivery is
# unreliable as of 2024+). Treat SMS as best-effort and use NTFY_TOPIC
# (push notification) and EMAIL_TO as the primary alert channels.
sms_gateways = {
    "Virgin": "vmobile.ca",
    "Bell": "txt.bell.ca",
    "MTS": "text.mtsmobility.com",
    "Rogers": "pcs.rogers.com",
    "Telus": "msg.telus.com",
    "Fido": "fido.ca",
    "Freedom": "txt.freedommobile.ca",
    "Koodo": "msg.telus.com",
    "Koodoo": "msg.telus.com",  # kept for backwards compatibility
    "PC": "mobiletxt.ca",
    "Sasktel": "sms.sasktel.com",
}
