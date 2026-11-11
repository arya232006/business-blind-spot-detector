-- Business Blind Spot Detector - initial schema (PostgreSQL)
-- Generated from database/models.py - do not edit by hand.

CREATE TABLE companies (
	id SERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	industry VARCHAR(120), 
	description TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE analysis_sessions (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	progress INTEGER NOT NULL, 
	message VARCHAR(300), 
	error TEXT, 
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	customer_source_ids JSON, 
	company_source_ids JSON, 
	n_customer INTEGER NOT NULL, 
	n_company INTEGER NOT NULL, 
	is_synthetic BOOLEAN NOT NULL, 
	overview JSON, 
	meta JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);
CREATE INDEX ix_analysis_sessions_company_id ON analysis_sessions (company_id);

CREATE TABLE data_sources (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	source_type VARCHAR(20) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	filename VARCHAR(300), 
	origin_url VARCHAR(1000), 
	is_synthetic BOOLEAN NOT NULL, 
	n_records INTEGER NOT NULL, 
	validation JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);
CREATE INDEX ix_data_sources_company_id ON data_sources (company_id);

CREATE TABLE aspect_sentiments (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	record_id INTEGER NOT NULL, 
	topic_id INTEGER NOT NULL, 
	clause TEXT NOT NULL, 
	aspect VARCHAR(120), 
	compound FLOAT NOT NULL, 
	label VARCHAR(12) NOT NULL, 
	similarity FLOAT, 
	explicit BOOLEAN NOT NULL, 
	signals JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_aspect_sentiments_session_id ON aspect_sentiments (session_id);
CREATE INDEX ix_aspect_session_topic ON aspect_sentiments (session_id, topic_id);

CREATE TABLE blind_spot_results (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	topic_id INTEGER NOT NULL, 
	topic_label VARCHAR(300) NOT NULL, 
	keywords JSON, 
	rank INTEGER NOT NULL, 
	classification VARCHAR(40) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	score FLOAT NOT NULL, 
	importance FLOAT NOT NULL, 
	gap FLOAT NOT NULL, 
	trend FLOAT, 
	trend_used FLOAT NOT NULL, 
	trend_available BOOLEAN NOT NULL, 
	trend_status VARCHAR(40), 
	mentions INTEGER NOT NULL, 
	unique_customers INTEGER NOT NULL, 
	share_pct FLOAT NOT NULL, 
	negative_pct FLOAT NOT NULL, 
	neg_pct FLOAT NOT NULL, 
	explicit_share_pct FLOAT NOT NULL, 
	frequency_score FLOAT NOT NULL, 
	customers_score FLOAT NOT NULL, 
	sentiment_score FLOAT NOT NULL, 
	explicit_score FLOAT NOT NULL, 
	coverage_share FLOAT NOT NULL, 
	coverage_norm FLOAT NOT NULL, 
	similarity FLOAT NOT NULL, 
	similarity_norm FLOAT NOT NULL, 
	growth_score FLOAT, 
	negative_trend_score FLOAT, 
	trend_enough BOOLEAN NOT NULL, 
	recurring BOOLEAN NOT NULL, 
	evidence_quotes JSON, 
	closest_company_messages JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_blind_spot_results_session_id ON blind_spot_results (session_id);

CREATE TABLE business_recommendations (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	topic_id INTEGER NOT NULL, 
	topic_label VARCHAR(300) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	problem TEXT NOT NULL, 
	evidence JSON, 
	blind_spot_score FLOAT NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	suggested_action TEXT NOT NULL, 
	expected_impact TEXT NOT NULL, 
	priority VARCHAR(20) NOT NULL, 
	classification VARCHAR(40), 
	llm_enhanced BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_business_recommendations_session_id ON business_recommendations (session_id);

CREATE TABLE company_communications (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	data_source_id INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	source VARCHAR(200), 
	date TIMESTAMP WITHOUT TIME ZONE, 
	category VARCHAR(120), 
	extra JSON, 
	is_synthetic BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE CASCADE
);
CREATE INDEX ix_company_communications_company_id ON company_communications (company_id);
CREATE INDEX ix_company_communications_data_source_id ON company_communications (data_source_id);

CREATE TABLE company_messaging_themes (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	theme_id INTEGER NOT NULL, 
	label VARCHAR(300) NOT NULL, 
	keywords JSON, 
	n_messages INTEGER NOT NULL, 
	share_pct FLOAT NOT NULL, 
	examples JSON, 
	sources JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_company_messaging_themes_session_id ON company_messaging_themes (session_id);

CREATE TABLE customer_conversations (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	data_source_id INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	source VARCHAR(200), 
	date TIMESTAMP WITHOUT TIME ZONE, 
	category VARCHAR(120), 
	customer_id VARCHAR(120), 
	rating FLOAT, 
	extra JSON, 
	is_synthetic BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE CASCADE
);
CREATE INDEX ix_customer_conversations_company_id ON customer_conversations (company_id);
CREATE INDEX ix_customer_conversations_data_source_id ON customer_conversations (data_source_id);

CREATE TABLE customer_expectations (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	topic_id INTEGER NOT NULL, 
	topic_label VARCHAR(300), 
	kind VARCHAR(40) NOT NULL, 
	summary TEXT NOT NULL, 
	is_inferred BOOLEAN NOT NULL, 
	support_count INTEGER NOT NULL, 
	share_pct FLOAT NOT NULL, 
	keywords JSON, 
	evidence JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_customer_expectations_session_id ON customer_expectations (session_id);

CREATE TABLE detected_topics (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	topic_id INTEGER NOT NULL, 
	label VARCHAR(300) NOT NULL, 
	category VARCHAR(60), 
	keywords JSON, 
	representative_docs JSON, 
	mentions INTEGER NOT NULL, 
	conversations INTEGER NOT NULL, 
	unique_customers INTEGER NOT NULL, 
	share_pct FLOAT NOT NULL, 
	avg_sentiment FLOAT NOT NULL, 
	positive_pct FLOAT NOT NULL, 
	negative_pct FLOAT NOT NULL, 
	neutral_pct FLOAT NOT NULL, 
	neg_intensity FLOAT NOT NULL, 
	explicit_share_pct FLOAT NOT NULL, 
	frequency_score FLOAT NOT NULL, 
	customers_score FLOAT NOT NULL, 
	sentiment_score FLOAT NOT NULL, 
	explicit_score FLOAT NOT NULL, 
	importance FLOAT NOT NULL, 
	volume_change_pct FLOAT, 
	trend_status VARCHAR(40), 
	score FLOAT, 
	severity VARCHAR(20), 
	classification VARCHAR(40), 
	PRIMARY KEY (id), 
	UNIQUE (session_id, topic_id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_detected_topics_session_id ON detected_topics (session_id);

CREATE TABLE trend_metrics (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	topic_id INTEGER, 
	kind VARCHAR(20) NOT NULL, 
	period TIMESTAMP WITHOUT TIME ZONE, 
	payload JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_trend_metrics_session_id ON trend_metrics (session_id);
CREATE INDEX ix_trend_session_kind ON trend_metrics (session_id, kind);

CREATE TABLE sentiment_results (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	conversation_id INTEGER, 
	record_id INTEGER NOT NULL, 
	text_original TEXT NOT NULL, 
	text_clean TEXT NOT NULL, 
	language VARCHAR(10), 
	source VARCHAR(200), 
	date TIMESTAMP WITHOUT TIME ZONE, 
	customer_id VARCHAR(120), 
	vader_compound FLOAT NOT NULL, 
	transformer_score FLOAT, 
	compound FLOAT NOT NULL, 
	label VARCHAR(12) NOT NULL, 
	model VARCHAR(200) NOT NULL, 
	topic_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES analysis_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES customer_conversations (id) ON DELETE SET NULL
);
CREATE INDEX ix_sentiment_results_session_id ON sentiment_results (session_id);
CREATE INDEX ix_sentiment_session_topic ON sentiment_results (session_id, topic_id);
