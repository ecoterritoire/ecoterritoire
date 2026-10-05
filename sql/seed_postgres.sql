-- Compte de demonstration uniquement. Changez le mot de passe en production.
INSERT INTO app_users (username, password_hash, role)
VALUES (
	'admin',
	'pbkdf2_sha256$310000$00000000000000000000000000000000$2bd2209a75048e2a7b6633e010c0e78c2920bf82c4ccb8dd62cada71abc8b8b0',
	'admin'
)
ON CONFLICT (username) DO NOTHING;

-- Cle publique du dashboard de developpement.
-- Elle est volontairement visible dans client-web/app.js et ne doit pas etre
-- utilisee en production.
INSERT INTO api_tokens (token_hash, description, is_active)
VALUES (
	'c03ca8c453b4778685e0a002d0d0272d9788323266633bb2d333978e6e32b393',
	'Dashboard public - developpement uniquement',
	TRUE
)
ON CONFLICT (token_hash) DO NOTHING;

-- Cle de demonstration pour le client mobile.
-- Token brut de developpement : eco_mobile_client_dev.
-- Ne pas utiliser cette cle en production.
INSERT INTO api_tokens (token_hash, description, is_active)
VALUES (
	'8865f0d4da216c44ff64485312ca79b47b81be2c31c74fff518afc57880b9d1c',
	'Client mobile - developpement uniquement',
	TRUE
)
ON CONFLICT (token_hash) DO NOTHING;
