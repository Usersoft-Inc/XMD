# XMD — END USER LICENSE AGREEMENT (EULA)

**Product:** XMD  
**Product Version:** 2.0  
**Revision Date:** 16.11.2026  
**Developer and Copyright Holder:** Usersoft Inc.

---

## 1. General Provisions

1.1. This End User License Agreement (hereinafter referred to as the "Agreement") establishes the terms and conditions governing the use of the XMD software product, version 2.0.

1.2. The XMD product consists of the following software components:

- **XMD** — a command-line shell with a command-line interface;
- **XMD COMMANDER** — a file manager featuring a three-panel interface, integrated into XMD and also distributed as a standalone application.

1.3. The developer and copyright holder of the product is Usersoft Inc. (hereinafter referred to as the "Developer").

1.4. Installation, launching, or use of any of the product's executable files (`xmd.exe`, `xmd_commander.exe`, `xmd.py`, `commander.py`) constitutes acceptance of the terms of this Agreement.

1.5. The product is distributed free of charge.

## 2. Subject Matter and Grant of License

2.1. The Developer grants the User a non-exclusive, royalty-free license to use XMD for personal purposes and internal business operations.

2.2. The license grants the User the right to:

- install and run the product;
- use the functionality of XMD and XMD COMMANDER;
- create backup copies of the software files;
- use the product on devices owned by the User, subject to the terms of this Agreement.

2.3. Transfer of the license to third parties is not permitted.

2.4. The User retains all rights to files and other materials created or modified using XMD.

2.5. The product may contain third-party open-source software components. The use of such components is governed by the respective licenses of their copyright holders.

2.6. Document OpenLicence OL-005-16112026 is intended for the internal record-keeping of the creation, publication, and distribution of Usersoft Inc.'s proprietary products during the period from 16.11.2026 to 16.11.2028. It does not replace this Agreement, modify the validity period of the end-user license, or supersede the licenses governing third-party components.

## 3. User Rights and Restrictions

3.1. The User is entitled to use XMD for file system navigation, viewing and editing files, and executing commands provided by the product.

3.2. The User is entitled to create backup copies of the software files and transfer the product between devices owned by the User.

3.3. The User is entitled to examine the product's behavior and functionality to the extent necessary for its proper operation.

3.4. The User is prohibited from:

- selling, leasing, or sublicensing the product;
- removing or modifying copyright notices or product names;
- distributing modified copies under the XMD name without the Developer's consent;
- using the product to engage in unlawful activities;
- gaining unauthorized access to data or systems belonging to third parties.

3.5. The User bears sole responsibility for the results of executing commands that may lead to the deletion, relocation, or overwriting of data.

Such operations include, but are not limited to:

- `rm`;
- `add -del`;
- `xsh -del`;
- `write -ow`;
- file and directory relocation operations.

3.6. The Developer recommends creating backup copies of important data before performing operations that may modify or delete file system contents.

## 4. Disclaimer of Warranties

4.1. The product is provided on an "AS IS" basis.

4.2. The Developer makes no warranties that the product:

- will fully meet the User's individual expectations;
- will operate continuously and without errors;
- will be compatible with all software and hardware configurations;
- will function without failures under all operating conditions.

4.3. The Developer undertakes no obligation to provide technical support, release updates, or develop new versions of the product.

## 5. Limitation of Liability

5.1. To the extent permitted by applicable law, the Developer shall not be liable for:

- loss of or damage to User data;
- loss of profits;
- equipment or software downtime;
- direct or indirect damages arising from the use of, or inability to use, the product.

5.2. The Developer's total aggregate liability under this Agreement shall be limited to the amount actually paid by the User for the product.

5.3. Since the product is distributed free of charge, the aforementioned amount is zero.

## 6. Privacy and Data Processing

6.1. XMD operates locally on the User's device and does not transmit User data to the Developer's external servers.

6.2. The product does not employ telemetry to collect User information.

6.3. Local activity logs and error reports may be generated to ensure the proper operation and diagnostics of the product.

Primary storage locations:

- activity log: `data/xmd/logs/actions.log`;
- crash reports: `data/xmd/crash_reports`;
- alternative data location: `%LOCALAPPDATA%\XMD\data\xmd`.

6.4. Content entered by the User when executing write commands is masked and is not stored in the activity log.

6.5. The User is solely responsible for safeguarding local logs and reports if they contain confidential information.

## 7. Third-Party Software Components

7.1. XMD uses third-party software components required for the product's operation.

7.2. In particular, the following technologies are used:

| Component | Version | License |
|---|---|---|
| Python | 3.15 | PSF License |
| PyQt6 / Qt | 6.12 | GPL v3 or Riverbank Computing Commercial License |
| PyInstaller | Current version | GPL v2 with an exception for distributed applications |

7.3. The use, distribution, and other activities involving third-party components are governed by the terms of their respective licenses.

7.4. This Agreement does not replace or restrict any rights granted to Users under the licenses of third-party components.

## 8. License Term and Termination

8.1. The license becomes effective upon the first launch of the product and remains valid until the User ceases using it.

8.2. In the event of a breach of the terms of this Agreement, the license may be terminated.

8.3. Following termination of the license due to a breach of its terms, the User must cease using the product and delete all copies of the software in their possession.

## 9. Amendments to the Agreement

9.1. The Developer reserves the right to amend the terms of this Agreement upon the release of new product versions.

9.2. An updated version of the Agreement may be distributed together with a new version of XMD or included in its documentation.

9.3. Continued use of a new version of the product constitutes acceptance of the updated terms of this Agreement.

## 10. Final Provisions

10.1. The parties shall endeavor to resolve any issues or disputes arising in connection with this Agreement through negotiations.

10.2. If a dispute cannot be resolved through negotiations, it shall be subject to resolution in accordance with applicable law.

---

**Developer and Copyright Holder:** Usersoft Inc.  
**Product:** XMD v2.0  
**Revision Date:** 16.11.2026

This document forms part of the official XMD product documentation and is distributed together with the software.
