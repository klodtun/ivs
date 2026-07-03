"use client";
import { useLang } from "@/components/lang-provider";

export default function ConsultingPage() {
  const { t } = useLang();

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("consulting.title")}</h1>
        <p className="text-gray-600 leading-relaxed">{t("consulting.body")}</p>
      </div>

      <div className="border border-gray-200 rounded-xl p-6 space-y-4 bg-amber-50">
        <h2 className="font-semibold text-gray-800 text-lg">{t("consulting.coffee")}</h2>
        <div>
          <style>{`.pp-N697H8TV6HSBL{text-align:center;border:none;border-radius:0.25rem;min-width:11.625rem;padding:0 2rem;height:2.625rem;font-weight:bold;background-color:#FFD140;color:#000000;font-family:"Helvetica Neue",Arial,sans-serif;font-size:1rem;line-height:1.25rem;cursor:pointer;}`}</style>
          <form
            action="https://www.paypal.com/ncp/payment/N697H8TV6HSBL"
            method="post"
            target="_blank"
            style={{ display: "inline-grid", justifyItems: "center", alignContent: "start", gap: "0.5rem" }}
          >
            <input className="pp-N697H8TV6HSBL" type="submit" value="เลี้ยงกาแฟทีม IVS" />
            <img src="https://www.paypalobjects.com/images/Debit_Credit.svg" alt="cards" />
            <section style={{ fontSize: "0.75rem" }}>
              ให้บริการโดย{" "}
              <img
                src="https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-wordmark-color.svg"
                alt="paypal"
                style={{ height: "0.875rem", verticalAlign: "middle" }}
              />
            </section>
          </form>
        </div>
      </div>

      <div className="border border-gray-200 rounded-xl p-6 space-y-2 bg-white">
        <h2 className="font-semibold text-gray-800 text-lg">{t("consulting.contact_label")}</h2>
        <p className="text-gray-700 font-medium">{t("consulting.contact_name")}</p>
        <p className="text-gray-600">
          e-mail:{" "}
          <a
            href={`mailto:${t("consulting.contact_email")}`}
            className="text-brand-600 hover:underline"
          >
            {t("consulting.contact_email")}
          </a>
        </p>
      </div>
    </div>
  );
}
