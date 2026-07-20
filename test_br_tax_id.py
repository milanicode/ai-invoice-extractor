"""Quick unit checks for BR emitente enrichment (no API)."""

from br_tax_id import (
    cnpj_from_access_key,
    enrich_invoice_data,
    find_vendor_name,
    format_cnpj,
    is_valid_cnpj,
)


def test_cnpj_from_access_key_bling_sample():
    key = "43090890627936000130550010000001750008965365"
    assert len(key) == 44
    cnpj = cnpj_from_access_key(key)
    assert cnpj == "90.627.936/0001-30"
    assert is_valid_cnpj(cnpj)


def test_cnpj_from_incomplete_chave_still_works():
    key = "4309089062793600013055001000000175000896536"
    assert cnpj_from_access_key(key) == "90.627.936/0001-30"


def test_enrich_fills_from_access_key_field():
    data = {
        "vendor_name": "Bling",
        "vendor_tax_id": None,
        "access_key": "43090890627936000130550010000001750008965365",
        "notes": "EXEMPLO",
    }
    out = enrich_invoice_data(data)
    assert out["vendor_tax_id"] == "90.627.936/0001-30"


def test_enrich_corrects_invalid_cnpj_using_chave():
    data = {
        "vendor_tax_id": "09.067.936/0001-30",
        "access_key": "4309089062793600013055001000000175000896536",
    }
    out = enrich_invoice_data(data)
    assert out["vendor_tax_id"] == "90.627.936/0001-30"


def test_enrich_fills_vendor_name_from_text():
    data = {"vendor_name": None}
    out = enrich_invoice_data(data, source_text="Emitente: EMPRESA MODELO LTDA")
    assert out["vendor_name"] == "EMPRESA MODELO LTDA"


def test_find_vendor_name_prefers_emitente():
    text = "Destinatário: COMÉRCIO VAREJISTA EXEMPLO LTDA\nEmitente: Bling Sistemas LTDA"
    assert find_vendor_name(text) == "Bling Sistemas LTDA"


if __name__ == "__main__":
    test_cnpj_from_access_key_bling_sample()
    test_cnpj_from_incomplete_chave_still_works()
    test_enrich_fills_from_access_key_field()
    test_enrich_corrects_invalid_cnpj_using_chave()
    test_enrich_fills_vendor_name_from_text()
    test_find_vendor_name_prefers_emitente()
    print("br_tax_id tests OK")
