import type { Ref } from 'react'
import { RedactableDemoText } from './RedactableDemoText'

type Props = {
  pageRef: Ref<HTMLDivElement>
}

/**
 * Synthetic Turkish reasoned decision ("Gerekçeli Karar").
 *
 * Structure, section ordering and drafting style follow the conventions of a
 * Turkish criminal judgment, but the proceeding is entirely fictional: every
 * name, identifier, address, date, case number and factual allegation is
 * demonstration data invented for this animation.
 */
export function DemoCourtDocument({ pageRef }: Props) {
  return (
    <div className="demo-page" data-demo-document="court" lang="tr" ref={pageRef}>
      <div className="demo-watermark">ÖRNEK BELGE · DEMO İÇERİK</div>

      <div className="demo-court-head" data-anchor="top">
        <div>T.C.</div>
        <div>
          <RedactableDemoText id="courtCity">İSTANBUL</RedactableDemoText>
        </div>
        <div>
          <RedactableDemoText id="courtName">1. AĞIR CEZA MAHKEMESİ</RedactableDemoText>
        </div>
      </div>

      <div className="demo-rows demo-rows-tight">
        <div className="demo-row">
          <span className="demo-row-label">DOSYA NO</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="caseFile">2099/999</RedactableDemoText> Esas
          </span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">KARAR NO</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="caseDecision">2099/777</RedactableDemoText>
          </span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">C.SAVCILIĞI ESAS NO</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="caseProsecution">2099/12345</RedactableDemoText>
          </span>
        </div>
      </div>

      <div className="demo-title-block">
        <div className="demo-title">GEREKÇELİ KARAR</div>
        <div className="demo-title demo-title-spaced">T Ü R K &nbsp; M İ L L E T İ &nbsp; A D I N A</div>
      </div>

      <div className="demo-rows">
        <div className="demo-row">
          <span className="demo-row-label">BAŞKAN</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="president">ÖRNEK BAŞKAN 99999</RedactableDemoText>
          </span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">ÜYE</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="memberOne">DENEME ÜYE 88888</RedactableDemoText>
          </span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">ÜYE</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="memberTwo">TEST ÜYE 77777</RedactableDemoText>
          </span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">C. SAVCISI</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="prosecutor">ÖRNEK SAVCI 66666</RedactableDemoText>
          </span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">KATİP</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="clerk">DEMO KATİP 55555</RedactableDemoText>
          </span>
        </div>
      </div>

      <div className="demo-rows" data-anchor="parties">
        <div className="demo-row">
          <span className="demo-row-label">DAVACI</span>
          <span className="demo-row-value">: K.H.</span>
        </div>

        <div className="demo-row">
          <span className="demo-row-label">KATILAN</span>
          <span className="demo-row-value demo-row-justify">
            : <RedactableDemoText id="partyName">ÖRNEK KİŞİ</RedactableDemoText>,{' '}
            <RedactableDemoText id="partyParents">Deneme ve Örnek</RedactableDemoText> kızı,{' '}
            <RedactableDemoText id="partyBirthDate">01/01/2072</RedactableDemoText>{' '}
            <RedactableDemoText id="partyBirthPlace">İSTANBUL / BAKIRKÖY</RedactableDemoText>{' '}
            doğumlu, mah/köy nüfusuna kayıtlı,{' '}
            <RedactableDemoText id="partyAddress">
              Örnek Mah. Deneme Sok. No: 8 D: 4 İstanbul
            </RedactableDemoText>{' '}
            adresinde oturur. T.C. Kimlik No:{' '}
            <RedactableDemoText id="partyId">10000000146</RedactableDemoText>. Telefon:{' '}
            <RedactableDemoText id="partyPhone">0532 123 45 67</RedactableDemoText>
          </span>
        </div>

        <div className="demo-row">
          <span className="demo-row-label">VEKİLİ</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="partyCounsel">Av. ÖRNEK AVUKAT</RedactableDemoText>,
          </span>
        </div>

        <div className="demo-row">
          <span className="demo-row-label">SANIK</span>
          <span className="demo-row-value demo-row-justify">
            : <RedactableDemoText id="accusedName">DENEME KİŞİ</RedactableDemoText>,{' '}
            <RedactableDemoText id="accusedParents">Örnek ve Test</RedactableDemoText> oğlu,{' '}
            <RedactableDemoText id="accusedBirthDate">02/02/2070</RedactableDemoText> doğumlu, mah/köy
            nüfusuna kayıtlı,{' '}
            <RedactableDemoText id="accusedAddress">
              Deneme Mah. Örnek Cad. No: 18 İç Kapı No: 8 Demo Apt.
            </RedactableDemoText>{' '}
            adresinde oturur. T.C. Kimlik No:{' '}
            <RedactableDemoText id="accusedId">10000000146</RedactableDemoText>
          </span>
        </div>

        <div className="demo-row">
          <span className="demo-row-label">MÜDAFİİ</span>
          <span className="demo-row-value">
            : <RedactableDemoText id="accusedCounsel">Av. DENEME AVUKAT</RedactableDemoText>,
          </span>
        </div>
      </div>

      <div className="demo-rows demo-rows-tight">
        <div className="demo-row">
          <span className="demo-row-label">SUÇ</span>
          <span className="demo-row-value">: Mala Zarar Verme, Tehdit</span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">SUÇ TARİHİ</span>
          <span className="demo-row-value">: 12/02/2099</span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">SUÇ YERİ</span>
          <span className="demo-row-value">: İSTANBUL / BAHÇELİEVLER</span>
        </div>
        <div className="demo-row">
          <span className="demo-row-label">KARAR TARİHİ</span>
          <span className="demo-row-value">: 09/09/2099</span>
        </div>
      </div>

      <div className="demo-rule" />

      <div className="demo-prose">
        <p>
          Yukarıda açık kimliği yazılı sanık hakkında mahkememizde yapılan açık yargılama sonunda
          dosya incelendi, gereği düşünüldü:
        </p>

        <p className="demo-heading" data-anchor="claim">
          İDDİA:
        </p>
        <p>
          <RedactableDemoText id="bodyCity">İstanbul</RedactableDemoText> Cumhuriyet
          Başsavcılığının{' '}
          <RedactableDemoText id="bodyDate">12/03/2099</RedactableDemoText> tarihli,{' '}
          <RedactableDemoText id="bodyCaseNo">2099/12345</RedactableDemoText> soruşturma,{' '}
          <RedactableDemoText id="bodyCaseNoTwo">2099/6789</RedactableDemoText> esas ve{' '}
          <RedactableDemoText id="bodyCaseNoThree">2099/4567</RedactableDemoText> sayılı iddianamesi
          ile; <RedactableDemoText id="bodyAccusedOne">sanık DENEME KİŞİ'nin</RedactableDemoText>{' '}
          olay tarihinde katılan{' '}
          <RedactableDemoText id="bodyPartyOne">ÖRNEK KİŞİ</RedactableDemoText>'ye ait iş
          yerinin giriş kapısına vurmak suretiyle zarar verdiği ve aynı olay sırasında katılana
          yönelik tehdit içeren sözler söylediğinden bahisle, eylemlerine uyan sevk maddeleri
          gereğince cezalandırılması istemi ile mahkememize kamu davası açılmıştır.
        </p>

        <p className="demo-heading" data-anchor="defense">
          SAVUNMA:
        </p>
        <p>
          <span className="demo-inline-heading">
            SANIK <RedactableDemoText id="bodyAccusedTwo">DENEME KİŞİ</RedactableDemoText>{' '}
            SAVUNMASINDA:
          </span>{' '}
          “Katılan <RedactableDemoText id="bodyPartyTwo">ÖRNEK KİŞİ</RedactableDemoText>'yi aynı
          mahallede oturmamız nedeniyle öteden beri tanırım. Olay günü{' '}
          <RedactableDemoText id="bodyAddress">Örnek Mah. Deneme Sok. No: 24</RedactableDemoText>{' '}
          sayılı adresin önünden geçmekteydim. Aramızda daha önce kira meselesinden kaynaklanan bir
          anlaşmazlık bulunduğu için karşılıklı olarak kısa süreli bir tartışma yaşandı. Ancak
          katılanın iş yerine herhangi bir zarar vermedim, kendisine tehdit içeren bir söz de
          söylemedim. Üzerime atılı suçlamaları kabul etmiyorum, beraatime karar verilmesini talep
          ederim.” şeklinde savunmada bulunmuş; müdafii{' '}
          <RedactableDemoText id="bodyCounsel">Av. DENEME AVUKAT</RedactableDemoText> da savunmaya
          iştirak etmiştir.
        </p>

        <p className="demo-heading" data-anchor="statements">
          KATILAN BEYANI:
        </p>
        <p>
          <span className="demo-inline-heading">
            KATILAN <RedactableDemoText id="bodyPartyThree">ÖRNEK KİŞİ</RedactableDemoText>{' '}
            BEYANINDA:
          </span>{' '}
          “Sanık <RedactableDemoText id="bodyAccusedThree">DENEME KİŞİ</RedactableDemoText>'yi aynı
          mahallede oturması nedeniyle tanırım. Olay günü{' '}
          <RedactableDemoText id="bodyAddressTwo">Örnek Mah. Deneme Sok. No: 24</RedactableDemoText>{' '}
          sayılı adreste bulunan iş yerimde çalıştığım sırada dışarıdan gürültü geldi. Kapının önüne
          çıktığımda sanığı gördüm, aramızda kısa süreli bir tartışma yaşandı. Sanık olay yerinden
          ayrıldıktan sonra iş yerinin giriş kapısında hasar meydana geldiğini fark ettim. Olay
          nedeniyle şikâyetçiyim, davaya katılmak istiyorum.” şeklinde beyanda bulunmuştur.
        </p>

        <p className="demo-heading" data-anchor="witness">TANIK BEYANI:</p>
        <p>
          <span className="demo-inline-heading">
            TANIK <RedactableDemoText id="bodyWitnessOne">TEST KİŞİ</RedactableDemoText>{' '}
            BEYANINDA:
          </span>{' '}
          “Sanık <RedactableDemoText id="bodyAccusedFour">DENEME KİŞİ</RedactableDemoText> ile katılan{' '}
          <RedactableDemoText id="bodyPartyFour">ÖRNEK KİŞİ</RedactableDemoText>'yi mahalleden
          tanırım, kendileriyle herhangi bir husumetim yoktur. Olay günü iş yerinin karşısındaki
          durakta beklemekteydim. Tarafların bir süre konuştuklarını, ardından aralarında yüksek
          sesli bir tartışma çıktığını gördüm. Sanığın kısa süre sonra olay yerinden ayrıldığını
          gördüm; ancak iş yerinin giriş kapısındaki hasarın ne şekilde meydana geldiğini
          görmedim.” şeklinde beyanda bulunmuştur.
        </p>

        <p className="demo-heading" data-anchor="opinion">
          İDDİA MAKAMI ESAS HAKKINDAKİ MÜTALAASINDA:
        </p>
        <p>
          “Dosya kapsamı, sanık savunması, katılan beyanı, tanık anlatımı, olay yeri tespit tutanağı
          ve hasar tespit tutanağı birlikte değerlendirildiğinde; sanık{' '}
          <RedactableDemoText id="bodyAccusedFive">DENEME KİŞİ</RedactableDemoText>'nin üzerine atılı
          mala zarar verme suçunu işlediğinin sabit olduğu, tehdit suçu yönünden ise takdirin
          mahkemeye ait olduğu anlaşılmakla, eylemine uyan ilgili kanun maddeleri gereğince
          cezalandırılmasına karar verilmesi kamu adına talep ve mütalaa olunur.” şeklinde görüş
          bildirmiştir.
        </p>

        <p className="demo-heading">DELİLLER:</p>
        <div className="demo-list">
          <div>1- Sanık savunması,</div>
          <div>2- Katılan beyanı ve katılma talebi,</div>
          <div>3- Tanık beyanı,</div>
          <div>4- Olay yeri tespit tutanağı,</div>
          <div>5- Hasar tespit tutanağı ve dosyada bulunan fotoğraflar,</div>
          <div>6- Adli sicil kaydı,</div>
          <div>7- Dosya kapsamındaki sair bilgi ve belgeler.</div>
        </div>

        <p className="demo-heading" data-anchor="reasoning">
          DELİLLERİN DEĞERLENDİRİLMESİ VE GEREKÇE:
        </p>
        <p>
          Sanık savunması, katılan beyanı, tanık anlatımı ile dosya kapsamında bulunan olay yeri
          tespit tutanağı ve hasar tespit tutanağı bir bütün halinde değerlendirildiğinde; her ne
          kadar sanık <RedactableDemoText id="bodyAccusedSix">DENEME KİŞİ</RedactableDemoText> üzerine
          atılı suçlamaları kabul etmemiş ise de, katılan{' '}
          <RedactableDemoText id="bodyPartyFive">ÖRNEK KİŞİ</RedactableDemoText>'nin
          aşamalardaki beyanlarının kendi içerisinde tutarlı olduğu, tanık{' '}
          <RedactableDemoText id="bodyWitnessTwo">TEST KİŞİ</RedactableDemoText>'nin anlatımının
          katılan beyanını tarafların olay yerinde tartıştığı yönünden doğruladığı, olay yeri tespit
          tutanağı ile hasar tespit tutanağı içeriğinin katılanın iddiası ile örtüştüğü, buna karşılık
          sanığın savunmasının dosya kapsamındaki diğer delillerle desteklenmediği anlaşılmıştır. Bu
          itibarla sanığın mala zarar verme suçunu işlediği sabit görülmüş; tehdit suçu yönünden ise
          katılan beyanı dışında mahkûmiyete yeterli, her türlü şüpheden uzak, kesin ve inandırıcı
          delil elde edilemediği, tanık anlatımının bu yönde bir tespit içermediği,{' '}
          <RedactableDemoText id="bodyCaseNoFour">2099/999</RedactableDemoText> esas sayılı dosya
          kapsamının da bu sonucu değiştirmediği anlaşılmakla, mahkememizce aşağıdaki şekilde hüküm
          kurulmuştur.
        </p>

        <p className="demo-heading" data-anchor="ruling">
          HÜKÜM: Gerekçesi yukarıda açıklandığı üzere;
        </p>
        <div className="demo-list">
          <div>
            1- Sanık <RedactableDemoText id="bodyAccusedSeven">DENEME KİŞİ</RedactableDemoText>'nin
            mala zarar verme suçundan, eylemine uyan ilgili kanun maddeleri gereğince
            CEZALANDIRILMASINA,
          </div>
          <div>
            2- Sanık hakkında tehdit suçundan açılan kamu davası yönünden, atılı suçu işlediği her
            türlü şüpheden uzak biçimde ispatlanamadığından BERAATİNE,
          </div>
          <div>
            3- Katılan{' '}
            <RedactableDemoText id="bodyPartySix">ÖRNEK KİŞİ</RedactableDemoText>'nin davaya
            katılma talebinin kabulü ile, kendisini vekil ile temsil ettirdiği anlaşıldığından
            katılan lehine vekâlet ücretine hükmedilmesine,
          </div>
          <div>
            4- Katılan vekili{' '}
            <RedactableDemoText id="bodyCounselTwo">Av. ÖRNEK AVUKAT</RedactableDemoText> tarafından
            yapıldığı anlaşılan yargılama giderlerinin sanıktan tahsili ile hazineye irat kaydına,
          </div>
          <div>
            5- Kararın taraflara tebliği ile, tebliğden itibaren yasal süresi içerisinde kanun
            yoluna başvurulabileceğinin ihtarına,
          </div>
        </div>
        <p>
          Dair; katılan vekili ile sanık müdafiinin yüzünde, Cumhuriyet savcısının katılımı ile
          verilen karar açıkça okunup usulen anlatıldı. 09/09/2099
        </p>
      </div>

      <div className="demo-sign">
        <div>
          <span className="demo-sign-role">BAŞKAN</span>
          <span>
            <RedactableDemoText id="president">ÖRNEK BAŞKAN 99999</RedactableDemoText>
          </span>
        </div>
        <div>
          <span className="demo-sign-role">ÜYE</span>
          <span>
            <RedactableDemoText id="memberOne">DENEME ÜYE 88888</RedactableDemoText>
          </span>
        </div>
        <div>
          <span className="demo-sign-role">ÜYE</span>
          <span>
            <RedactableDemoText id="memberTwo">TEST ÜYE 77777</RedactableDemoText>
          </span>
        </div>
        <div>
          <span className="demo-sign-role">KATİP</span>
          <span>
            <RedactableDemoText id="clerk">DEMO KATİP 55555</RedactableDemoText>
          </span>
        </div>
      </div>

      <div className="demo-page-foot">
        <span>1/5</span>
        <span className="demo-page-foot-note">
          Bu belge örnek amaçlıdır ve gerçek bir yargı kararı değildir.
        </span>
      </div>
    </div>
  )
}
