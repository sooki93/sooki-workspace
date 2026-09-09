from alembic import op
revision="0001"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.execute('CREATE TABLE users (\n\tid VARCHAR(36) NOT NULL, \n\temail VARCHAR(255) NOT NULL, \n\trole VARCHAR NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (email)\n)')
    op.execute('CREATE TABLE brand_settings (\n\tuser_id VARCHAR(36) NOT NULL, \n\trules JSONB NOT NULL, \n\tcategory_mapping JSONB NOT NULL, \n\tcategories JSONB NOT NULL, \n\tPRIMARY KEY (user_id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute('CREATE TABLE cafe24_accounts (\n\tid VARCHAR(36) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\tmall_id VARCHAR(64) NOT NULL, \n\taccess_token TEXT NOT NULL, \n\trefresh_token TEXT NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdemo BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (user_id), \n\tFOREIGN KEY(user_id) REFERENCES users (id), \n\tUNIQUE (mall_id)\n)')
    op.execute('CREATE TABLE jobs (\n\tid VARCHAR(36) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(30) NOT NULL, \n\ttarget_id VARCHAR(36) NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tmessage TEXT NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute("CREATE UNIQUE INDEX one_pending_job ON jobs (user_id, kind, target_id) WHERE status IN ('QUEUED', 'RUNNING')")
    op.execute('CREATE INDEX ix_jobs_user_id ON jobs (user_id)')
    op.execute('CREATE TABLE login_sessions (\n\tid VARCHAR(64) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute('CREATE TABLE oauth_states (\n\tid VARCHAR(64) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\tsession_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute('CREATE TABLE source_products (\n\tid VARCHAR(36) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\tproduct_no INTEGER NOT NULL, \n\tproduct_name TEXT NOT NULL, \n\tproduct_group VARCHAR NOT NULL, \n\tcreated_date VARCHAR(64) NOT NULL, \n\tthumbnail TEXT NOT NULL, \n\tparsed JSONB NOT NULL, \n\timage_hashes JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (user_id, product_no), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute('CREATE INDEX ix_source_products_user_id ON source_products (user_id)')
    op.execute('CREATE TABLE template_profiles (\n\tid VARCHAR(36) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\tmall_id VARCHAR(64) NOT NULL, \n\tbrand VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tanalysis JSONB NOT NULL, \n\tsource_product_ids JSONB NOT NULL, \n\tglobal_template JSONB NOT NULL, \n\tcategory_templates JSONB NOT NULL, \n\tstyles JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tactivated_at TIMESTAMP WITH TIME ZONE, \n\tarchived_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (user_id, version), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute('CREATE INDEX ix_template_profiles_user_id ON template_profiles (user_id)')
    op.execute("CREATE UNIQUE INDEX one_active_profile ON template_profiles (user_id) WHERE status = 'ACTIVE'")
    op.execute('CREATE TABLE products (\n\tid VARCHAR(36) NOT NULL, \n\tuser_id VARCHAR(36) NOT NULL, \n\tcafe24_product_no INTEGER, \n\tbrand VARCHAR NOT NULL, \n\tinternal_product_group VARCHAR NOT NULL, \n\tcafe24_category_id INTEGER, \n\tstatus VARCHAR NOT NULL, \n\trevision INTEGER NOT NULL, \n\treviewed_revision INTEGER, \n\ttemplate_profile_id VARCHAR(36), \n\ttemplate_snapshot JSONB NOT NULL, \n\tproduct_name TEXT NOT NULL, \n\tprice INTEGER, \n\tsupply_price INTEGER, \n\tdescription TEXT NOT NULL, \n\tmaterial TEXT NOT NULL, \n\tsize TEXT NOT NULL, \n\tkeywords JSONB NOT NULL, \n\tseo JSONB NOT NULL, \n\tai_result JSONB NOT NULL, \n\treference_product_id VARCHAR(36), \n\tmain_image_id VARCHAR(36), \n\trendered_html TEXT NOT NULL, \n\twarnings JSONB NOT NULL, \n\tupload_steps JSONB NOT NULL, \n\tmessage TEXT NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id), \n\tFOREIGN KEY(template_profile_id) REFERENCES template_profiles (id)\n)')
    op.execute('CREATE INDEX ix_products_user_id ON products (user_id)')
    op.execute('CREATE TABLE ai_generations (\n\tid VARCHAR(36) NOT NULL, \n\tproduct_id VARCHAR(36) NOT NULL, \n\tinput JSONB NOT NULL, \n\toutput JSONB NOT NULL, \n\tmodel VARCHAR(100) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(product_id) REFERENCES products (id)\n)')
    op.execute('CREATE TABLE product_images (\n\tid VARCHAR(36) NOT NULL, \n\tproduct_id VARCHAR(36) NOT NULL, \n\tfile_url TEXT NOT NULL, \n\tstorage_key TEXT NOT NULL, \n\tfile_hash VARCHAR(64) NOT NULL, \n\tperceptual_hash VARCHAR(64) NOT NULL, \n\timage_type VARCHAR NOT NULL, \n\tai_confidence FLOAT NOT NULL, \n\tconfirmed BOOLEAN NOT NULL, \n\tsort_order INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(product_id) REFERENCES products (id)\n)')
    op.execute('CREATE INDEX ix_product_images_file_hash ON product_images (file_hash)')
    op.execute('CREATE INDEX ix_product_images_product_id ON product_images (product_id)')

def downgrade():
    op.execute('DROP TABLE product_images')
    op.execute('DROP TABLE ai_generations')
    op.execute('DROP TABLE products')
    op.execute('DROP TABLE template_profiles')
    op.execute('DROP TABLE source_products')
    op.execute('DROP TABLE oauth_states')
    op.execute('DROP TABLE login_sessions')
    op.execute('DROP TABLE jobs')
    op.execute('DROP TABLE cafe24_accounts')
    op.execute('DROP TABLE brand_settings')
    op.execute('DROP TABLE users')
