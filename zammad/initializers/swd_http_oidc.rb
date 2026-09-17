# SWD/omniauth_openid_connect bauen die Discovery-URL immer mit URI::HTTPS (:443),
# unabhängig vom Issuer-Schema. Lokal hängt Keycloak hinter Traefik auf HTTP.
# Produktion: ZAMMAD_HTTP_TYPE=https — dieser Block bleibt aus.
Rails.application.config.after_initialize do
  next unless ENV['ZAMMAD_HTTP_TYPE'] == 'http'
  next unless defined?(SWD)

  SWD.url_builder = URI::HTTP
end
