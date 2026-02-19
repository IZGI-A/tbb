# Panel Regresyon Modelleri

**Kaynak:** Colak, Deniz, Korkmaz & Yilmaz (2024) — TCMB Working Paper 24/09
"A Panorama of Liquidity Creation in Turkish Banking Industry"

**Donem:** 2025/9 (kesitsel)
**Yontem:** OLS (tek donem)
**Orneklem:** 33 mevduat bankasi (kalkinma/yatirim bankalari ve sistem toplamlari haric)
**Veri Kaynagi:** ClickHouse `tbb.financial_statements` tablosu (TBB bilanco ve gelir tablosu verileri)

---

## Veri Hazirlama

### ClickHouse Sorgusu

`financial_statements` tablosundan `year_id = 2025, month_id = 9` donemi icin banka bazinda asagidaki kalemler cekilir:

| Alan | ClickHouse Filtresi | Aciklama |
|------|---------------------|----------|
| `equity` | `main_statement = '2. YUKUMLULUKLER'` + `child_statement = 'XVI. OZKAYNAKLAR'` | Ozkaynaklar |
| `total_assets` | `main_statement = '1. VARLIKLAR'` + `child_statement = 'XI. VARLIKLAR TOPLAMI'` | Toplam varliklar |
| `net_income` | `main_statement = '4. GELIR-GIDER TABLOSU / 5. KAR VEYA ZARAR'` + `child_statement = 'XXV. DONEM NET KARI/ZARARI'` | Net kar |
| `liquid_assets` | Nakit ve Nakit Benzerleri + Gercege Uygun Deger Farki K/Z FV + Gercege Uygun Deger Farki DKG FV | Likit varliklar |
| `semi_liquid_assets` | Turev Finansal Varliklar + Kiralama Alacaklari + Faktoring + Itfa Edilmis Diger FV + Satis Amacli Varliklar + Ortaklik Yatirimlari + Cari/Ertelenmis Vergi | Yari-likit varliklar |
| `illiquid_assets` | Krediler + Maddi Duran Varliklar + Maddi Olmayan Duran Varliklar + Yatirim Amacli Gayrimenkuller + Diger Aktifler | Likit olmayan varliklar |
| `liquid_liabilities` | Mevduat + Alinan Krediler + Para Piyasalarina Borclar + Fonlar + GUD Farki K/Z Finansal Yukumlulukler | Likit yukumlulukler |
| `illiquid_liabilities_equity` | Ihrac Edilen Menkul Kiymetler + Kiralama Yukumlulukleri + Sermaye Benzeri Borclanma + Ozkaynaklar | Likit olmayan yukumlulukler + ozkaynak |

### Haric Tutulan Bankalar

Sistem toplamlari, grup toplamlari, kalkinma/yatirim bankalari ve TMSF bankalari haric tutulur. Orneklem yalnizca **mevduat bankalarini** icerir.

### Hesaplanan Degiskenler

Her banka icin asagidaki degiskenler hesaplanir:

| Degisken | Formul | Aciklama |
|----------|--------|----------|
| `lc_nonfat` | `[0.5 * (illiq_assets + liq_liab) + 0 * semi_assets - 0.5 * (liq_assets + illiq_liab_eq)] / total_assets` | Likidite yaratimi orani (Cat-Nonfat, Berger & Bouwman 2009) |
| `capital_adequacy` | `(equity / total_assets) - 0.08` | Sermaye yeterliligi (%8 esik ustu) |
| `roa` | `net_income / total_assets` | Aktif karliligi |
| `bank_size` | `ln(total_assets)` | Banka buyuklugu (dogal logaritma) |
| `state` | `1` kamu bankasi ise, `0` digerleri | Kamu sahipligi (binary) |
| `competition` | `1 / HHI` burada `HHI = sum(pazar_payi_i^2)`, `pazar_payi_i = banka_aktifleri / toplam_sistem_aktifleri` | Rekabet endeksi (Herfindahl-Hirschman tersine cevrimi) |
| `z_score` | `(capital_ratio + ROA) / \|ROA\|` | Banka riski gostergesi (tek donem: ROA mutlak degeri kullanilir) |

### Kamu Bankalari

State = 1 olarak isaretlenen bankalar:
- T.C. Ziraat Bankasi A.S.
- Turkiye Halk Bankasi A.S.
- Turkiye Vakiflar Bankasi T.A.O.

### On Isleme

Tum surekli degiskenler **%1 ve %99 percentile** degerlerinde winsorize edilir (asiri uclari kirpma).

---

## Model 1 — Denklem (2): Sermaye Yeterliligi -> Likidite Yaratimi

```
LC_i = alpha + beta * CapitalAdequacy_i + theta1 * BankSize_i + theta2 * ROA_i + epsilon_i
```

**Amac:** Banka sermaye yeterliligi ile likidite yaratimi arasindaki iliskiyi test etmek. Makalede iki karsi hipotez var:
- *Risk absorpsiyon hipotezi:* Yuksek sermaye -> daha fazla likidite yaratimi
- *Finansal kirilganlik hipotezi:* Yuksek sermaye -> daha az likidite yaratimi

| Rol | Degisken | Veri |
|-----|----------|------|
| Bagimli (Y) | `lc_nonfat` | Cat-Nonfat likidite yaratimi / toplam aktifler |
| Bagimsiz (X1) | `capital_adequacy` | Ozkaynak / toplam aktifler - 0.08 |
| Kontrol (X2) | `bank_size` | ln(toplam aktifler) |
| Kontrol (X3) | `roa` | Net kar / toplam aktifler |

---

## Model 2 — Denklem (3): Rekabet -> Likidite Yaratimi

```
LC_i = alpha + beta * Competition_i + theta1 * BankSize_i + theta2 * ROA_i + epsilon_i
```

**Amac:** Sektor duzeyinde rekabetin likidite yaratimi uzerindeki etkisini incelemek.
- Competition = 1/HHI: Daha yuksek deger = daha fazla rekabet
- HHI = sum(pazar_payi^2): Herbir bankanin aktif buyuklugunu toplam sistem aktiflerine bolup, karesini alip, toplam

| Rol | Degisken | Veri |
|-----|----------|------|
| Bagimli (Y) | `lc_nonfat` | Cat-Nonfat likidite yaratimi / toplam aktifler |
| Bagimsiz (X1) | `competition` | 1 / HHI (tum bankalarin pazar paylarindan hesaplanir) |
| Kontrol (X2) | `bank_size` | ln(toplam aktifler) |
| Kontrol (X3) | `roa` | Net kar / toplam aktifler |

### HHI Hesaplama Detayi

```
pazar_payi_i = banka_i_toplam_aktifleri / sektor_toplam_aktifleri
HHI = sum(pazar_payi_i ^ 2)  (tum bankalar icin)
Competition = 1 / HHI
```

Ornekte 33 banka kullanildigi icin, esit dagilim varsayiminda HHI = 33 * (1/33)^2 = 1/33, Competition = 33.
Gercekte buyuk bankalar daha fazla pazar payina sahip oldugundan HHI daha yuksek, Competition daha dusuktur.

---

## Model 3 — Denklem (4): Kamu Sahipligi -> Likidite Yaratimi

```
LC_i = alpha + beta * State_i + theta1 * BankSize_i + theta2 * ROA_i + epsilon_i
```

**Amac:** Kamu sahipliginin likidite yaratimi uzerindeki etkisini test etmek. Makalenin bulgularina gore kamu bankalari genellikle daha fazla likidite yaratma egilimindedir.

| Rol | Degisken | Veri |
|-----|----------|------|
| Bagimli (Y) | `lc_nonfat` | Cat-Nonfat likidite yaratimi / toplam aktifler |
| Bagimsiz (X1) | `state` | 1 = kamu bankasi (Ziraat, Halk, Vakif), 0 = diger |
| Kontrol (X2) | `bank_size` | ln(toplam aktifler) |
| Kontrol (X3) | `roa` | Net kar / toplam aktifler |

**Not:** Makalede bu modelde banka sabit etkisi (delta_i) kullanilmaz cunku `state` degiskeni bankalar arasi degismez (time-invariant degil, entity-invariant). Zaman sabit etkisi (gamma_t) kullanilir ancak tek donemde bu da uygulanamaz.

---

## Model 4 — Denklem (5): Likidite Yaratimi -> Banka Riski

```
ZScore_i = alpha + beta * LC_i + theta1 * BankSize_i + theta2 * ROA_i + epsilon_i
```

**Amac:** Likidite yaratiminin banka riski uzerindeki etkisini olcmek. Makalede iki karsi hipotez var:
- *Yuksek likidite yaratimi hipotezi:* Daha fazla LC -> daha fazla risk (dusuk Z-Score)
- *Risk azaltma hipotezi:* Daha fazla LC -> daha az risk (yuksek Z-Score)

| Rol | Degisken | Veri |
|-----|----------|------|
| Bagimli (Y) | `z_score` | (Ozkaynak orani + ROA) / \|ROA\| |
| Bagimsiz (X1) | `lc_nonfat` | Cat-Nonfat likidite yaratimi / toplam aktifler |
| Kontrol (X2) | `bank_size` | ln(toplam aktifler) |
| Kontrol (X3) | `roa` | Net kar / toplam aktifler |

### Z-Score Hesaplama Detayi

```
capital_ratio = equity / total_assets
Z-Score = (capital_ratio + ROA) / |ROA|
```

Yuksek Z-Score = dusuk risk (banka iflastan uzak).
Tek donem oldugu icin sigma(ROA) yerine |ROA| kullanilir. Coklu donem oldugunda banka bazinda ROA'nin standart sapmasi kullanilir.

---

## Likidite Yaratimi (Cat-Nonfat) Formulu

Berger & Bouwman (2009) cercevesine dayanan likidite yaratimi hesaplamasi:

```
LC = [ 0.5 * (likit olmayan varliklar + likit yukumlulukler)
     + 0.0 * (yari-likit varliklar + yari-likit yukumlulukler)
     - 0.5 * (likit varliklar + likit olmayan yukumlulukler + ozkaynak)
     ] / toplam aktifler
```

**Mantik:**
- Likit olmayan varliklari likit yukumluluklerle finanse etmek likidite **yaratir** (agirlik: +0.5)
- Yari-likit kalemler **notr** (agirlik: 0)
- Likit varliklari likit olmayan yukumluluklerle finanse etmek likidite **yok eder** (agirlik: -0.5)

### Bilancodaki Siniflandirma

| Kategori | Varliklar | Yukumlulukler |
|----------|-----------|---------------|
| **Likit** | Nakit, GUD Farki K/Z FV, GUD Farki DKG FV | Mevduat, Alinan Krediler, Para Piyasasi Borclari, Fonlar, GUD Farki K/Z Fin. Yuk. |
| **Yari-likit** | Turev FV, Kiralama Alacak., Faktoring, Itfa Edilmis Diger FV, Satis Amacli Varlik, Ortaklik Yat., Vergi Varliklari | *(yok)* |
| **Likit olmayan** | Krediler, Maddi Duran Varlik, Maddi Olmayan DV, Yatirim Amacli Gayr., Diger Aktifler | Ihrac Edilen MK, Kiralama Yuk., Sermaye Benzeri Borc, Ozkaynaklar |

---

## Teknik Detaylar

| Parametre | Deger |
|-----------|-------|
| Tahmin Yontemi | OLS (statsmodels) |
| Donem | 2025/9 (kesitsel) |
| Muhasebe Sistemi | Varsayilan: SOLO (filtre ile degistirilebilir) |
| Winsorize | %1 ve %99 percentile |
| Cache | Redis, TTL: 3600 saniye |
| API Endpoint | `GET /api/panel-regression/results?accounting_system=SOLO` |
| Servis Dosyasi | `source/api/services/panel_regression_service.py` |
| Frontend Sayfasi | `frontend/src/pages/PanelRegression.tsx` |

### Coklu Donem Destegi

Kod, birden fazla donem verisi mevcut oldugunda otomatik olarak **Panel FE** (LSDV) yontemine gecer:
- Gecikme degiskenleri (t-1) eklenir
- Banka sabit etkileri (delta_i): LSDV dummy degiskenleri + cluster-robust standart hatalar
- Zaman sabit etkileri (gamma_t): LSDV dummy degiskenleri
- Z-Score hesaplamasinda sigma(ROA) banka bazinda donelmer arasi standart sapma olarak hesaplanir

Su an veri tabaninda tek donem (2025/9) filtrelendigi icin kesitsel OLS uygulanmaktadir.
