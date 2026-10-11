{#-
  Hashing standard (see data/docs/standards/data_vault_standards.md):
    * MD5, output as upper-case hex string (32 chars)
    * each value: CAST to STRING, TRIM, UPPER
    * NULL or blank value -> '^^'
    * multiple columns joined with '||'
    * hash keys use business keys in the order given
    * hashdiffs use descriptive columns sorted alphabetically
-#}

{% macro _hash_parts(columns) -%}
    {%- set parts = [] -%}
    {%- for c in columns -%}
        {%- do parts.append("COALESCE(NULLIF(UPPER(TRIM(CAST(" ~ c ~ " AS STRING))), ''), '^^')") -%}
    {%- endfor -%}
    {{ parts | join(", '||', ") }}
{%- endmacro %}

{% macro hash_key(columns) -%}
    {%- if columns is string -%}{%- set columns = [columns] -%}{%- endif -%}
    UPPER(TO_HEX(MD5(CONCAT({{ _hash_parts(columns) }}))))
{%- endmacro %}

{% macro hash_diff(columns) -%}
    {%- if columns is string -%}{%- set columns = [columns] -%}{%- endif -%}
    UPPER(TO_HEX(MD5(CONCAT({{ _hash_parts(columns | sort) }}))))
{%- endmacro %}

{#- A business key is valid when it is not NULL and not blank. -#}
{% macro is_valid_bk(column) -%}
    ({{ column }} IS NOT NULL AND TRIM(CAST({{ column }} AS STRING)) != '')
{%- endmacro %}

{#- Normalised business key value stored in hubs. -#}
{% macro clean_bk(column) -%}
    UPPER(TRIM(CAST({{ column }} AS STRING)))
{%- endmacro %}
