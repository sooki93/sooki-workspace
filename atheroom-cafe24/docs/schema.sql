-- PostgreSQL initial schema. Managed by Alembic.

CREATE TABLE users (
	id VARCHAR(36) NOT NULL,
	email VARCHAR(255) NOT NULL,
	role VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
);

CREATE TABLE brand_settings (
	user_id VARCHAR(36) NOT NULL,
	rules JSONB NOT NULL,
	category_mapping JSONB NOT NULL,
	categories JSONB NOT NULL,
	PRIMARY KEY (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE cafe24_accounts (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	mall_id VARCHAR(64) NOT NULL,
	access_token TEXT NOT NULL,
	refresh_token TEXT NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	demo BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	UNIQUE (mall_id)
);

CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	kind VARCHAR(30) NOT NULL,
	target_id VARCHAR(36) NOT NULL,
	status VARCHAR NOT NULL,
	message TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE UNIQUE INDEX one_pending_job ON jobs (user_id, kind, target_id) WHERE status IN ('QUEUED', 'RUNNING');

CREATE INDEX ix_jobs_user_id ON jobs (user_id);

CREATE TABLE login_sessions (
	id VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE oauth_states (
	id VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	session_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE source_products (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	product_no INTEGER NOT NULL,
	product_name TEXT NOT NULL,
	product_group VARCHAR NOT NULL,
	created_date VARCHAR(64) NOT NULL,
	thumbnail TEXT NOT NULL,
	parsed JSONB NOT NULL,
	image_hashes JSONB NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id, product_no),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_source_products_user_id ON source_products (user_id);

CREATE TABLE template_profiles (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	mall_id VARCHAR(64) NOT NULL,
	brand VARCHAR NOT NULL,
	version INTEGER NOT NULL,
	status VARCHAR NOT NULL,
	analysis JSONB NOT NULL,
	source_product_ids JSONB NOT NULL,
	global_template JSONB NOT NULL,
	category_templates JSONB NOT NULL,
	styles JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	activated_at TIMESTAMP WITH TIME ZONE,
	archived_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (user_id, version),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_template_profiles_user_id ON template_profiles (user_id);

CREATE UNIQUE INDEX one_active_profile ON template_profiles (user_id) WHERE status = 'ACTIVE';

CREATE TABLE products (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	cafe24_product_no INTEGER,
	brand VARCHAR NOT NULL,
	internal_product_group VARCHAR NOT NULL,
	cafe24_category_id INTEGER,
	status VARCHAR NOT NULL,
	revision INTEGER NOT NULL,
	reviewed_revision INTEGER,
	template_profile_id VARCHAR(36),
	template_snapshot JSONB NOT NULL,
	product_name TEXT NOT NULL,
	price INTEGER,
	supply_price INTEGER,
	description TEXT NOT NULL,
	material TEXT NOT NULL,
	size TEXT NOT NULL,
	option_settings JSONB DEFAULT '{}' NOT NULL,
	keywords JSONB NOT NULL,
	seo JSONB NOT NULL,
	ai_result JSONB NOT NULL,
	reference_product_id VARCHAR(36),
	main_image_id VARCHAR(36),
	rendered_html TEXT NOT NULL,
	warnings JSONB NOT NULL,
	upload_steps JSONB NOT NULL,
	message TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(template_profile_id) REFERENCES template_profiles (id)
);

CREATE INDEX ix_products_user_id ON products (user_id);

CREATE TABLE ai_generations (
	id VARCHAR(36) NOT NULL,
	product_id VARCHAR(36) NOT NULL,
	input JSONB NOT NULL,
	output JSONB NOT NULL,
	model VARCHAR(100) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE product_images (
	id VARCHAR(36) NOT NULL,
	product_id VARCHAR(36) NOT NULL,
	file_url TEXT NOT NULL,
	storage_key TEXT NOT NULL,
	file_hash VARCHAR(64) NOT NULL,
	perceptual_hash VARCHAR(64) NOT NULL,
	image_type VARCHAR NOT NULL,
	ai_confidence FLOAT NOT NULL,
	confirmed BOOLEAN NOT NULL,
	sort_order INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_product_images_file_hash ON product_images (file_hash);

CREATE INDEX ix_product_images_product_id ON product_images (product_id);
