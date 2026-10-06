import { hospital } from '../../config/hospital'
import styles from './Site.module.css'

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <p className={styles.footerName}>{hospital.name}</p>
        <dl className={styles.facts}>
          <div>
            <dt>Address</dt>
            <dd>{hospital.address}</dd>
          </div>
          <div>
            <dt>Main line</dt>
            <dd>
              <a href={`tel:${hospital.mainPhone.replace(/[^\d+]/g, '')}`}>{hospital.mainPhone}</a>
            </dd>
          </div>
          <div>
            <dt>Emergency</dt>
            <dd>
              <a href={`tel:${hospital.emergencyNumber}`}>{hospital.emergencyNumber}</a>
            </dd>
          </div>
          <div>
            <dt>Visiting hours</dt>
            <dd>{hospital.visitingHours}</dd>
          </div>
        </dl>
        <p className={styles.poweredBy}>Powered by Hospital Care</p>
      </div>
    </footer>
  )
}
