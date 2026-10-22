# Gold review

Ten Turkish and ten English documents, taken from the test split. The text is the document. The tables are empty on purpose: fill document id, exact text, and label. A notes column is there when you need to say which copy you mean. Do not write offsets.

## Turkish

### tr-test-mixed-001

```text
SULH PROTOKOLÜ

İstanbul 5. Asliye Ticaret Mahkemesi, esas 2021/330, 2021/331 ve 2021/332 sayılı dosyalarında taraflar bu protokolle anlaşmıştır. Davacı vekili Av. Nedim Kural protokolü kaleme almıştır.

Ödemeler, aşağıdaki altı hesaba üçer taksit hâlinde yapılacaktır:
1. taksit hesabı TR20 9999 9000 0000 0000 0000 14.
2. taksit hesabı TR90 9999 9000 0000 0000 0000 15.
3. taksit hesabı TR63 9999 9000 0000 0000 0000 16.
4. taksit hesabı TR36 9999 9000 0000 0000 0000 17.
5. taksit hesabı TR09 9999 9000 0000 0000 0000 18.
6. taksit hesabı TR79 9999 9000 0000 0000 0000 19.

Müvekkil T.C. 10000001136, doğum tarihleri kayıtlarda 01.01.1970 ve eş için 02.02.1972 olarak durmaktadır. Tebligat adresi: Bağdat Caddesi No: 200 Kadıköy/İstanbul ve yazlık için Sahil Yolu No: 9 Datça/Muğla. E-posta nedim.kural@example.com ile asistan@example.org, telefon +90 532 010 1108 ve +90 532 010 1109.

Protokol mahkeme huzurunda okunmuştur.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `9999 9000 0000 0000 0000` at 292, 343, 394, 445, 496, 547
- `+90 532 010` at 851, 871

### tr-test-contract-002

```text
BELİRSİZ SÜRELİ İŞ SÖZLEŞMESİ

İşbu sözleşme, işveren Tepe Nakliyat Ltd. Şti. ile işçi Baran Usta arasında 2 Nisan 2024 tarihinde kurulmuştur. İşçi, depo sorumlusu olarak çalışacaktır. İşçinin T.C. kimlik numarası 10000001372, doğum tarihi 11.04.1989'dur. İkamet adresi Tunalı Hilmi Caddesi No: 88 Çankaya/Ankara adresidir.

İşçinin görülen bir alacak davası vardır. Esas numarası 2018/2771'dir. Bu sözleşme o davanın tarafını değiştirmez.

Brüt aylık ücret 54.500 TL'dir. Ücret dört ayrı hesaba bölünerek ödenir:
1. hesap TR84 9999 9000 0000 0000 0000 26
2. hesap TR57 9999 9000 0000 0000 0000 27
3. hesap TR30 9999 9000 0000 0000 0000 28
4. hesap TR03 9999 9000 0000 0000 0000 29

Bildirimler baran.usta@example.com adresine ve insan kaynakları için ik@example.org adresine gönderilir. Acil durumda +90 532 010 1112 numarası aranır.

İşçi bir nüshayı teslim aldığını kabul eder.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `İşçinin` at 185, 325
- `9999 9000 0000 0000 0000` at 528, 570, 612, 654

### tr-test-judgment-001

```text
T.C.
ANTALYA 3. ASLİYE TİCARET MAHKEMESİ
Esas no: 2022/905 Karar no: 2024/311
Ek esas: 2022/906

Hâkim Lale Demirbaş başkanlığında yapılan yargılama sonunda:

Davacı: Keriman Uysal
Konu: Sözleşmenin uyarlanması istemidir.

Gerekçe: Davacı, 2020 tarihli tedarik sözleşmesinin bedelinin öngörülemez biçimde arttığını ileri sürmüştür. Davalı taraf cevap dilekçesinde borcu kabul etmiştir. Mahkeme, bedelin bilirkişi raporu çerçevesinde güncellenmesine karar vermiştir. Davacının doğum tarihi nüfus örneğinde 05.08.1969 olarak görünmektedir ve kimlik tespiti bu kayıtla yapılmıştır.

Hüküm: Davanın kısmen kabulüne, yargılama giderinin paylaşılmasına. Tebliğ için keriman.uysal@example.com ve +90 532 010 1105 kullanılacaktır.

Karar açıkça okundu.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `Karar` at 59, 724

### tr-test-neg-salary-001

```text
ÜCRET SKALASI DUYURUSU

İnsan kaynakları, 2024 yılı için kadro derecelerine bağlı örnek ücret bandını yayımlamıştır. Bu duyuru belirli bir çalışanı göstermez. Derece 1 için örnek brüt ücret 25.000 TL, derece 2 için 18.750 TL olarak ilan edilmiştir. Tutarlar bütçe taslağıdır.

4857 sayılı Kanun'un ücretin ödenmesine ilişkin hükümleri saklıdır. Başvuru formu bu duyurunun eki değildir.
```

No capitalised phrase, number, or email is repeated in this document.

### tr-test-neg-salary-002

```text
Kimden: Satın alma
Konu: Katalog fiyatları

Satın alma biriminin dikkatine,

Kırtasiye çerçevesinin güncel liste fiyatı 22.000 TL, kargo bedeli ayrıca 450 TL'dir. Bu rakamlar firma fiyat listesinden alınmıştır ve bir kişiye ödenen ücret değildir. Sipariş, stok kodu ile açılacaktır.

İyi çalışmalar.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `Satın alma` at 8, 44

### tr-test-ihtar-001

```text
İHTARNAME

Keşide eden: Gülseren Pamuk, 10000000450.
Muhatap: kiracı sıfatıyla taşınmazda oturan kişi.

Konu: 1 Mart 2024 başlangıçlı kira sözleşmesinin bedelinin ödenmemesi hakkında ihtardır.

Sayın muhatap, Şubat 2024 dönemine ait kira bedeli süresinde ödenmemiştir. İşbu ihtarın tebliğinden itibaren yedi gün içinde borcun kapatılmasını, aksi halde tahliye ve takip yollarına başvurulacağını bildiririm. Yazışma adresi: İnönü Caddesi No: 22 Konak/İzmir. E-posta gulseren.pamuk@example.com, telefon +90 532 010 1101.

İhtar eden
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `2024` at 117, 215

### tr-test-petition-001

```text
İZMİR 2. SULH HUKUK MAHKEMESİNE

Davacı: Sezgin Oral, T.C. 10000000528
Davalı: Handan Ersoy
Konu: Ortaklığın giderilmesi istemidir.

Açıklamalar: Taraflar, Karşıyaka'da kayıtlı taşınmazın paydaşıdır. Paylaşım konusunda anlaşma sağlanamamıştır. Esas numarası henüz verilmemiş olup harç makbuzunda 2024/120 dosya sırası yazılıdır. Dava, 4721 sayılı Kanun'un ilgili maddelerine dayanır.

Sonuç ve istem: Taşınmazın satış yoluyla ortaklığının giderilmesine karar verilsin.
```

No capitalised phrase, number, or email is repeated in this document.

### tr-test-poa-001

```text
VEKÂLETNAME

Ben, Aylin Peker (T.C. kimlik no 10000000696), bu vekâletname ile Rüya Deniz'i vekil tayin ediyorum. Vekil avukat değildir. Kendisi, benim adıma banka şubesinden hesap özeti almak, posta ile gelen tebligatı teslim almak ve apartman yönetimine dilekçe bırakmak konusunda yetkilidir. Dava açmak, sulh olmak veya bir avukat görevlendirmek bu yetkinin dışındadır.

Vekil, tebligatları Ihlamur Sokak No: 6 Alsancak/İzmir adresinden takip eder ve gerektiğinde +90 532 010 1102 numarasından bana ulaşır.

Bu belge 18 Nisan 2024 tarihinde iki nüsha düzenlenmiştir.

Vekâlet veren
```

No capitalised phrase, number, or email is repeated in this document.

### tr-test-hearing-001

```text
DURUŞMA TUTANAĞI

Bursa 1. Asliye Hukuk Mahkemesinde, dosya no 2024/640, 22 Mayıs 2024 günü saat 11.00'de duruşma açıldı.

Hâkim Kemal Örnek, tanık Feride Uslu'nun yeminli beyanını aldı. Tanık, olay günü sokakta bulunduğunu ve bağırış duyduğunu anlattı. Tarafların avukatları beyana diyeceklerinin olmadığını bildirdi. Mahkeme, eksik vekâlet pulunun tamamlanması için dosyanın bir sonraki güne bırakılmasına karar verdi.

Tutanak sesli okunarak imza altına alındı.
```

No capitalised phrase, number, or email is repeated in this document.

### tr-test-icra-001

```text
İCRA TAKİP TALEBİ

Ankara 6. İcra Dairesine,

Alacaklı: Yıldız Mert, T.C. 10000000764, adres: Tunalı Hilmi Caddesi No: 90 Kavaklıdere/Ankara, e-posta yildiz.mert@example.com, telefon +90 532 010 1103.
Borçlu: Cemre Dağ.
Dosya no: 2024/771.

Alacak, 14 Ocak 2024 tarihli cari hesaptan doğan 92.000 TL'dir. Tahsilat önce TR58 9999 9000 0000 0000 0000 09 hesabına, bakiye kalırsa TR31 9999 9000 0000 0000 0000 10 hesabına aktarılsın. Borçluya ödeme emri tebliğ edilsin.

Talep eden alacaklı
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `9999 9000 0000 0000 0000` at 324, 382

Add one row for each span. Copy the document id and the exact text. Leave the label as one of the types in the annotation guidelines. Offsets are filled in afterwards from the exact text.

| document id | exact text | label | notes |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

## English

### en-test-settlement-001

```text
SETTLEMENT AGREEMENT

Claim BL-2024-119 between the claimant Camille Duarte and the defendant Isaac Keller is settled on the following terms. The defendant will pay the agreed sum in two transfers, to GB41 TEST 0099 0000 0000 30 and GB14 TEST 0099 0000 0000 31.

The claimant's date of birth is 4 May 1975, national insurance number ZZ100003D, and passport GBX0000010. Notices go to 64 Station Road, York, camille.duarte31@example.com or 202-555-0131.

The parties will file a consent order. This agreement is the full and final settlement of that claim only.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `TEST 0099 0000 0000` at 206, 238

### en-test-share-001

```text
SHARE PURCHASE EXTRACT

The seller Colin Frost agrees to sell 40 ordinary shares in Grey Harbour Ltd to the buyer Marta Nguyen. Completion is conditional on the buyer paying the price into two seller accounts, GB69 TEST 0099 0000 0000 11 and GB42 TEST 0099 0000 0000 12.

The seller's notice address is 7 Harbour Walk, Glasgow. Questions before completion go to colin.frost13@example.com or 07700 900012.

Warranties are given on an indemnity basis. This extract is the operative payment clause of a longer sale agreement and is not a one-line schedule.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `Harbour` at 89, 305
- `TEST 0099 0000 0000` at 215, 247

### en-test-witness-001

```text
WITNESS STATEMENT

I, Denise Bennett, of 12 Chapel Road, Cardiff, date of birth 4 April 1978, state as follows. I make this statement for claim BL-2024-104 in which Philip Cross is the defendant. The statement was taken by Hannah Fleming, solicitor for the claimant.

On the evening in question I saw the defendant leave the yard and lock the gate. I then telephoned 07700 900016 and reported what I had seen. Crown Prosecutor Roger Rowe told the witness which allegations were in issue and said the charging decision would be reviewed after this statement was signed.

I believe the facts in this statement are true.
```

No capitalised phrase, number, or email is repeated in this document.

### en-test-neg-salary-001

```text
PAY BAND CIRCULAR

For budgeting only, band A is illustrated at GBP 42,000 a year and band B at GBP 55,000 a year. No employee is named. The figures are sample salaries for a grade, not a payment to an identifiable person.

Managers must not paste a real name into this circular.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `at GBP` at 61, 93

### en-test-neg-salary-002

```text
From: Finance
To: Payroll policy
Subject: Sample cost

The worked example in the handbook uses a salary of GBP 48,500 and a bonus of GBP 2,000. The example is a formula check. It is not attached to a member of staff.

Please leave the names blank when you circulate it.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `of GBP` at 104, 130

### en-test-judgment-001

```text
JUDGMENT EXTRACT

Justice Nell Underwood handed down judgment in appeal BL-2024-111. The Appellant, Lucia Spencer, who was the Claimant at first instance, appeals against the order dismissing the claim against Harvey Turner. The court below had preferred the defendant's account of the meeting.

The appeal is allowed in part. The matter is remitted for assessment of loss only. A further Appellant, Helen Carter, is named in the notice of appeal, but the papers do not say whether that person was the claimant or the defendant below.

Reasons were given in open court.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `Appellant,` at 89, 389

### en-test-engagement-001

```text
ENGAGEMENT LETTER

Dear Yusuf Underwood,

This firm, by Grace Hale, is instructed to advise you on the lease of the premises at 54 Castle Street, Edinburgh. Our fees are billed monthly to GB36 TEST 0099 0000 0000 23. We will write to yusuf.underwood27@example.com and may call 202-555-0127.

For identity checks we hold passport GBX0000006. Leonard Okonkwo is named as attorney-in-fact solely to receive papers while the client is abroad. The attorney-in-fact is not a solicitor or barrister, and the appointment is under a power of attorney.

Please sign and return the enclosed copy to confirm these terms.
```

No capitalised phrase, number, or email is repeated in this document.

### en-test-employment-001

```text
EMPLOYMENT AGREEMENT

This agreement is made between Northglass Supplies Ltd and Naomi Duarte. It is signed for the company by Hugo Keller, the human resources director.

The employee will work as an operations lead at 15 Cedar Lane, Bristol. The employee's date of birth is 14 March 1985 and national identifier 666-15-1005. Pay is GBP 65000 per year, paid monthly to GB37 TEST 0099 0000 0000 05.

Notices go to naomi.duarte5@example.com or 202-555-0104. The employee was the Applicant named in the vacancy notice for the post of operations lead.

Either party may end the employment on four weeks' written notice after the probation period.
```

These exact strings occur more than once. Offsets are Unicode code points, starting at 0. If you label one of them, say which offset you mean in the notes column.
- `The employee` at 171, 456

### en-test-court-order-001

```text
COURT ORDER

Before Judge Julian Lawson. Claim BL-2024-108.

Upon hearing counsel for the claimant Oscar Jarvis and for the defendant Beatrice Keane, it is ordered that the defendant file a defence within 14 days. The claimant's application for an injunction is adjourned to the next available date.

Costs of today are reserved. This order was drawn by the court and sealed the same day.
```

No capitalised phrase, number, or email is repeated in this document.

### en-test-lba-001

```text
LETTER BEFORE ACTION

Dear Sirs,

We act for the claimant Elliot Cross in contemplated proceedings under reference BL-2024-115. This letter is written by Naomi Fleming, counsel instructed for that claimant.

Our client demands repayment within 14 days to GB31 TEST 0099 0000 0000 16. Correspondence should be sent to 34 King Street, Manchester, emailed to elliot.cross17@example.com, or telephoned to 202-555-0120.

If payment is not received we are instructed to issue a claim without further notice.
```

No capitalised phrase, number, or email is repeated in this document.

Add one row for each span. Copy the document id and the exact text. Leave the label as one of the types in the annotation guidelines. Offsets are filled in afterwards from the exact text.

| document id | exact text | label | notes |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
