-- Volterra initial schema (spec section 4).

create table option_quotes (
    id bigserial primary key,
    source text not null,
    instrument text not null,
    underlying text not null,
    observed_at timestamptz not null,
    expiry timestamptz not null,
    strike double precision not null,
    option_type text not null check (option_type in ('call', 'put')),
    bid double precision,
    ask double precision,
    mark double precision,
    spot double precision not null,
    rate double precision not null,
    dividend_yield double precision not null default 0,
    implied_vol double precision,
    iv_status text,
    unique (source, instrument, observed_at)
);

create index option_quotes_surface_idx
on option_quotes (underlying, observed_at, expiry, strike);

create table surface_snapshots (
    id uuid primary key,
    underlying text not null,
    observed_at timestamptz not null,
    grid_json jsonb not null,
    diagnostics_json jsonb not null,
    model_params_json jsonb,
    model_version text
);
