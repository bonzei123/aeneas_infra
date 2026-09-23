# Keycloak-Gruppen → Zammad-Rollen und Ticket-Queues.
# Customer bleibt Standard (nur eigene Tickets). Agent sieht die Queue.
# Gruppen werden nicht entzogen, nur ergänzt.
module Aeneas
  module ZammadOidcAgent
    MAP = {
      'admin:zammad'   => { roles: %w[Agent], queues: { 'Users' => 'full' } },
      'zammad:support' => { roles: %w[Agent], queues: { 'Support' => 'full' } },
      'zammad:hr'      => { roles: %w[Agent], queues: { 'HR' => 'full' } },
      'zammad:admin'   => { roles: %w[Admin Agent], queues: { 'Users' => 'full', 'Support' => 'full', 'HR' => 'full' } },
    }.freeze

    def find_from_hash(hash)
      auth = super
      Aeneas::ZammadOidcAgent.apply(auth&.user, hash)
      auth
    end

    def create_from_hash(hash, user = nil)
      auth = super
      Aeneas::ZammadOidcAgent.apply(auth&.user, hash)
      auth
    end

    module_function

    def groups_of(hash)
      extra = hash['extra'] || hash[:extra] || {}
      raw = extra['raw_info'] || extra[:raw_info] || extra['id_info'] || {}
      raw = raw.to_h if raw.respond_to?(:to_h)
      info = hash['info'] || hash[:info] || {}
      names = Array(raw['groups'] || raw[:groups] || info['groups'])
      token = (hash['credentials'] || hash[:credentials] || {})['token']
      names += Array(jwt_groups(token))
      names.map { |x| x.to_s.sub(%r{\A/}, '') }.uniq
    end

    def jwt_groups(token)
      part = token.to_s.split('.')[1]
      return [] if part.blank?

      part += '=' * ((4 - part.length % 4) % 4)
      data = JSON.parse(Base64.urlsafe_decode64(part))
      Array(data['groups'])
    rescue StandardError
      []
    end

    def apply(user, hash)
      return if user.blank?

      wanted = groups_of(hash)
      specs = MAP.select { |g, _| wanted.include?(g) }.values
      return if specs.blank?

      role_names = specs.flat_map { |s| s[:roles] }.uniq
      queues = {}
      specs.each { |s| queues.merge!(s[:queues]) }

      role_names.each do |name|
        role = Role.lookup(name: name)
        next if role.blank?
        user.roles << role unless user.role?(name)
      end
      map = (user.group_names_access_map || {}).transform_keys(&:to_s)
      queues.each { |q, access| map[q] = access if map[q].blank? }
      user.group_names_access_map = map
      user.save!
    end
  end
end

Rails.application.config.to_prepare do
  Authorization.singleton_class.prepend(Aeneas::ZammadOidcAgent)
end
