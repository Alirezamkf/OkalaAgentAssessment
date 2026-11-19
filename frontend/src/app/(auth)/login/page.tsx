import type { Metadata } from "next";
import LoginForm from "@/components/hr/login-form";
import "@/styles/hr/login.css";

export const metadata: Metadata = {
  title: "ورود منابع انسانی | اکالا",
  description: "ورود کارشناسان منابع انسانی به سامانه ارزیابی استعداد اکالا",
};

export default function LoginPage() {
  return (
    <main className="hr-login" lang="fa" dir="rtl">
      <div className="container hr-login-container">
        <div className="hr-login-shell row g-0">
          <section className="hr-login-brand col-lg-5" aria-label="سامانه ارزیابی استعداد اکالا">
            <div className="hr-login-wordmark">
              <span className="hr-login-mark" aria-hidden="true"><span /></span>
              <span>اکالا</span>
            </div>
            <div className="hr-login-brand-copy">
              <span className="hr-login-eyebrow">منابع انسانی اکالا</span>
              <h2>سامانه ارزیابی <br />استعداد</h2>
              <p>فرصتی برای شناخت بهتر استعدادها و ساختن تیمی توانمند.</p>
              <div className="hr-login-brand-detail" aria-hidden="true"><span /><span /><span /></div>
            </div>
            <p className="hr-login-brand-footer">شناخت استعدادها، آغاز یک مسیر تازه</p>
          </section>
          <section className="hr-login-panel col-lg-7" aria-labelledby="hr-login-title">
            <div className="hr-login-form-wrap">
              <span className="hr-login-section-label">پنل منابع انسانی</span>
              <h1 id="hr-login-title">خوش آمدید</h1>
              <p className="hr-login-intro">برای ورود به سامانه، نام کاربری و رمز عبور خود را وارد کنید.</p>
              <LoginForm />
              <p className="hr-login-help">این صفحه ویژه کارشناسان منابع انسانی اکالا است.</p>
            </div>
          </section>
        </div>
        <footer className="hr-login-footer">اکالا · سامانه ارزیابی استعداد</footer>
      </div>
    </main>
  );
}
