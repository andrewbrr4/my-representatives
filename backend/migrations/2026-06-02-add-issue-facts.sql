-- Migration: add issue_id to facts + seed issue-themed loading facts
-- Date: 2026-06-02  (feature/issue-loading-facts)
--
-- This repo initializes from schema.sql against a *fresh* DB and keeps no
-- migration history. Databases created before this feature lack the
-- facts.issue_id column, which get_civics_facts() now references in BOTH the
-- general (issue_id IS NULL) and themed (issue_id = $1) query paths -- so an
-- un-migrated DB 500s on /api/facts. This script brings an existing DB up to
-- date. Idempotent: safe to run more than once.

ALTER TABLE facts ADD COLUMN IF NOT EXISTS issue_id text REFERENCES issues(id);

DO $migration$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM facts WHERE issue_id IS NOT NULL) THEN
    INSERT INTO facts (text, issue_id) VALUES
  -- abortion
  ('Roe v. Wade was decided by the Supreme Court in 1973 and overturned by Dobbs v. Jackson Women''s Health Organization in 2022.', 'abortion'),
  ('The Hyde Amendment, first enacted in 1976, generally prohibits federal Medicaid funds from being used for abortion services.', 'abortion'),
  ('Before Roe v. Wade, abortion laws were set entirely by individual states, with some permitting it and others criminalizing it.', 'abortion'),
  ('Planned Parenthood v. Casey (1992) allowed states to regulate abortion before fetal viability as long as no "undue burden" was imposed.', 'abortion'),
  ('After the Dobbs decision, individual states regained full authority to set their own abortion laws.', 'abortion'),
  -- affordable_housing
  ('The federal Housing Choice Voucher program (Section 8) helps about 2.3 million low-income households afford private-market rent.', 'affordable_housing'),
  ('The Low-Income Housing Tax Credit, created in 1986, is the primary federal tool for financing affordable rental housing construction.', 'affordable_housing'),
  ('Zoning laws, which are set at the local level, heavily influence how much housing can be built and at what density.', 'affordable_housing'),
  ('The U.S. Department of Housing and Urban Development was established in 1965 as a Cabinet-level agency.', 'affordable_housing'),
  ('Housing costs are generally considered unaffordable when they exceed 30 percent of a household''s gross income.', 'affordable_housing'),
  -- artificial_intelligence
  ('The term "artificial intelligence" was coined by computer scientist John McCarthy at a 1956 Dartmouth College workshop.', 'artificial_intelligence'),
  ('The EU AI Act, enacted in 2024, is one of the first comprehensive laws to regulate AI systems by risk level.', 'artificial_intelligence'),
  ('The U.S. federal government has no single AI-specific statute, though many agencies apply existing laws to AI-related activities.', 'artificial_intelligence'),
  ('Large language models like those used in modern chatbots are trained on vast text datasets using a technique called transformer architecture.', 'artificial_intelligence'),
  ('Congress has held numerous hearings on AI oversight and has debated whether to create a dedicated federal AI regulatory agency.', 'artificial_intelligence'),
  -- border_security
  ('U.S. Customs and Border Protection is the largest federal law enforcement agency by personnel, with roughly 60,000 employees.', 'border_security'),
  ('The U.S.-Mexico border stretches approximately 1,954 miles from the Pacific Ocean to the Gulf of Mexico.', 'border_security'),
  ('The Secure Fence Act of 2006 authorized construction of hundreds of miles of physical barriers along the southern border.', 'border_security'),
  ('Border Patrol was established in 1924 as part of the Labor Appropriation Act; it became part of DHS in 2003.', 'border_security'),
  ('The Department of Homeland Security was created in 2002 following the September 11, 2001 attacks, consolidating 22 federal agencies.', 'border_security'),
  -- campaign_finance
  ('The Federal Election Commission (FEC) was established in 1975 to enforce campaign finance laws for federal elections.', 'campaign_finance'),
  ('Citizens United v. FEC (2010) held that the First Amendment prohibits the government from restricting political spending by corporations and unions.', 'campaign_finance'),
  ('The Bipartisan Campaign Reform Act of 2002 (McCain-Feingold) banned unlimited "soft money" donations to national political parties.', 'campaign_finance'),
  ('Super PACs can raise and spend unlimited funds to support or oppose candidates but are prohibited from coordinating directly with campaigns.', 'campaign_finance'),
  ('Candidates for federal office must file public disclosure reports with the FEC detailing their fundraising and spending.', 'campaign_finance'),
  -- childcare
  ('The Child Care and Development Fund (CCDF) is the primary federal program that subsidizes childcare costs for low-income families.', 'childcare'),
  ('The United States has no universal publicly funded childcare system at the federal level, unlike many other wealthy nations.', 'childcare'),
  ('The Child Tax Credit, created in 1997, provides a per-child tax benefit that can reduce the tax liability of qualifying families.', 'childcare'),
  ('Head Start, launched in 1965, is a federal program providing early childhood education and support services to low-income children.', 'childcare'),
  ('Childcare workers rank among the lowest-paid occupations in the U.S. labor force, according to Bureau of Labor Statistics wage data.', 'childcare'),
  -- civil_rights
  ('The Civil Rights Act of 1964 prohibited discrimination based on race, color, religion, sex, or national origin in employment and public accommodations.', 'civil_rights'),
  ('The 14th Amendment, ratified in 1868, guarantees equal protection of the laws to all persons within U.S. jurisdiction.', 'civil_rights'),
  ('The Voting Rights Act of 1965 outlawed discriminatory voting practices that had disenfranchised Black Americans across the South.', 'civil_rights'),
  ('The Americans with Disabilities Act of 1990 prohibits discrimination against people with disabilities in employment, transportation, and public life.', 'civil_rights'),
  ('Title IX of the Education Amendments of 1972 prohibits sex-based discrimination in any education program receiving federal funding.', 'civil_rights'),
  -- climate_change
  ('The Paris Agreement, adopted in 2015, aims to limit global average temperature rise to well below 2 degrees Celsius above pre-industrial levels.', 'climate_change'),
  ('Carbon dioxide concentrations in Earth''s atmosphere have increased more than 50 percent since the pre-industrial era, according to NOAA data.', 'climate_change'),
  ('The Intergovernmental Panel on Climate Change (IPCC) was established in 1988 to assess scientific information on climate change.', 'climate_change'),
  ('The Inflation Reduction Act of 2022 authorized approximately $369 billion in climate and energy spending over a decade.', 'climate_change'),
  ('Sea levels have risen an average of about 8 to 9 inches globally since reliable record-keeping began around 1880.', 'climate_change'),
  -- criminal_justice_reform
  ('The U.S. has the highest incarceration rate of any nation, incarcerating roughly 2 million people at any given time.', 'criminal_justice_reform'),
  ('The First Step Act of 2018 reformed federal sentencing rules and expanded prisoner rehabilitation programs with bipartisan support.', 'criminal_justice_reform'),
  ('Mandatory minimum sentencing laws, introduced widely in the 1980s, require fixed prison terms regardless of individual circumstances.', 'criminal_justice_reform'),
  ('Private prisons house about 8 percent of the U.S. incarcerated population and are operated under contracts with federal and state governments.', 'criminal_justice_reform'),
  ('The Sixth Amendment guarantees the right to a speedy and public trial and the right to legal counsel in criminal prosecutions.', 'criminal_justice_reform'),
  -- economy
  ('The U.S. gross domestic product (GDP) is the largest of any single country, representing roughly one-quarter of global economic output.', 'economy'),
  ('The Federal Reserve, created by Congress in 1913, sets monetary policy and regulates banks to maintain economic stability.', 'economy'),
  ('The Bureau of Labor Statistics publishes the Consumer Price Index monthly to measure inflation across a basket of consumer goods.', 'economy'),
  ('A recession is commonly defined as two consecutive quarters of negative GDP growth, though the official determination is made by the NBER.', 'economy'),
  ('The U.S. national debt is the total amount the federal government owes to creditors including foreign governments and domestic bondholders.', 'economy'),
  -- education
  ('Public education in the United States is primarily funded and governed at the state and local level, not the federal level.', 'education'),
  ('The Every Student Succeeds Act of 2015 replaced No Child Left Behind and shifted more education authority back to states.', 'education'),
  ('Title I of the Elementary and Secondary Education Act directs federal funding to schools with high percentages of low-income students.', 'education'),
  ('The Department of Education was established as a Cabinet-level agency in 1979, having previously been part of HEW.', 'education'),
  ('Community colleges are two-year public institutions that offer associate degrees and vocational training at lower cost than four-year universities.', 'education'),
  -- energy_policy
  ('The Energy Policy Act of 2005 provided tax incentives and loan guarantees to expand U.S. energy production across multiple sources.', 'energy_policy'),
  ('The U.S. Energy Information Administration collects and publishes data on energy production, consumption, and prices nationwide.', 'energy_policy'),
  ('Nuclear power currently generates about 18 percent of U.S. electricity and produces no direct carbon dioxide emissions during operation.', 'energy_policy'),
  ('The Strategic Petroleum Reserve, established after the 1973 oil embargo, is the world''s largest government-owned oil stockpile.', 'energy_policy'),
  ('Renewable energy sources including wind and solar have grown to supply roughly 20 percent of U.S. electricity generation.', 'energy_policy'),
  -- environment
  ('The Environmental Protection Agency was established by executive order in 1970 under President Richard Nixon.', 'environment'),
  ('The Clean Air Act of 1970 authorized the federal government to set and enforce national air quality standards.', 'environment'),
  ('The Clean Water Act of 1972 established the basic structure for regulating pollutant discharges into U.S. waters.', 'environment'),
  ('The National Environmental Policy Act of 1970 requires federal agencies to assess the environmental impact of major projects.', 'environment'),
  ('The Superfund program, created in 1980, funds the cleanup of the most contaminated hazardous waste sites in the country.', 'environment'),
  -- foreign_policy
  ('The U.S. Constitution gives the president authority to conduct foreign policy, while Congress controls foreign aid and trade agreements.', 'foreign_policy'),
  ('The Senate must ratify treaties by a two-thirds supermajority, though many international agreements are handled as executive agreements instead.', 'foreign_policy'),
  ('The U.S. State Department, founded in 1789, is the oldest executive department and leads civilian overseas diplomatic efforts.', 'foreign_policy'),
  ('The United States has been a founding member of the United Nations since the UN Charter was signed in 1945.', 'foreign_policy'),
  ('Foreign aid amounts to less than 1 percent of the total federal budget in most years.', 'foreign_policy'),
  -- government_spending
  ('The federal government''s fiscal year runs from October 1 through September 30, and Congress is constitutionally required to pass spending bills.', 'government_spending'),
  ('Mandatory spending, which includes Social Security, Medicare, and Medicaid, accounts for roughly two-thirds of all federal spending.', 'government_spending'),
  ('The Congressional Budget Office provides independent economic and budget analyses to assist Congress in its oversight role.', 'government_spending'),
  ('A continuing resolution allows the government to keep operating at current funding levels when a formal appropriations bill hasn''t been passed.', 'government_spending'),
  ('The debt ceiling is a statutory limit on how much the federal government can borrow; Congress must vote to raise or suspend it.', 'government_spending'),
  -- gun_control
  ('The Second Amendment, ratified in 1791, protects the right to keep and bear arms; its scope has been debated and litigated extensively.', 'gun_control'),
  ('The Brady Handgun Violence Prevention Act of 1993 established the federal background check system for firearm purchases from licensed dealers.', 'gun_control'),
  ('The National Firearms Act of 1934 was the first major federal gun regulation, taxing and regulating machine guns and short-barreled rifles.', 'gun_control'),
  ('District of Columbia v. Heller (2008) established for the first time that the Second Amendment protects an individual right to own firearms.', 'gun_control'),
  ('The ATF (Bureau of Alcohol, Tobacco, Firearms and Explosives) is the primary federal agency that enforces federal firearms laws.', 'gun_control'),
  -- healthcare
  ('The Affordable Care Act, signed in 2010, expanded Medicaid eligibility and created insurance marketplaces for individuals to purchase coverage.', 'healthcare'),
  ('Medicare covers Americans aged 65 and older and certain younger people with disabilities; Medicaid covers low-income individuals of all ages.', 'healthcare'),
  ('The U.S. spends more on healthcare per capita than any other high-income nation, yet has lower life expectancy than many peers.', 'healthcare'),
  ('The Children''s Health Insurance Program (CHIP), created in 1997, provides coverage to children in families above the Medicaid threshold.', 'healthcare'),
  ('HIPAA (1996) set federal standards for protecting the privacy of patients'' medical information.', 'healthcare'),
  -- immigration
  ('The Immigration and Nationality Act of 1965 abolished national-origin quotas and gave priority to family reunification and skilled workers.', 'immigration'),
  ('About 1 million people become lawful permanent residents of the United States each year through various visa categories.', 'immigration'),
  ('DACA (Deferred Action for Childhood Arrivals) was established by executive action in 2012 to defer deportation of certain childhood arrivals.', 'immigration'),
  ('The U.S. Citizenship and Immigration Services (USCIS) processes immigration benefit applications within the Department of Homeland Security.', 'immigration'),
  ('Congress has the constitutional authority to set immigration law, including rules on who may enter and reside in the United States.', 'immigration'),
  -- infrastructure
  ('The Interstate Highway System, begun in 1956 under President Eisenhower, spans more than 48,000 miles of limited-access highways.', 'infrastructure'),
  ('The Infrastructure Investment and Jobs Act of 2021 allocated $1.2 trillion for roads, bridges, broadband, water, and transit projects.', 'infrastructure'),
  ('The American Society of Civil Engineers issues a periodic "Infrastructure Report Card" grading the condition of U.S. public infrastructure.', 'infrastructure'),
  ('The Army Corps of Engineers is the federal agency responsible for designing and building much of the nation''s water infrastructure.', 'infrastructure'),
  ('More than 40,000 U.S. bridges have been classified as structurally deficient, meaning they require significant maintenance or replacement.', 'infrastructure'),
  -- labor_rights
  ('The National Labor Relations Act of 1935 guarantees private-sector workers the right to organize and bargain collectively.', 'labor_rights'),
  ('The Fair Labor Standards Act of 1938 established the federal minimum wage, overtime pay, and child labor standards.', 'labor_rights'),
  ('The Occupational Safety and Health Act of 1970 created OSHA to set and enforce workplace safety and health standards.', 'labor_rights'),
  ('Union membership in the United States has declined from a peak of about 35 percent in the 1950s to roughly 10 percent today.', 'labor_rights'),
  ('Workers'' compensation programs, which cover job-related injuries and illnesses, are administered by each individual state.', 'labor_rights'),
  -- lgbtq_rights
  ('The Supreme Court''s Obergefell v. Hodges decision (2015) established a constitutional right to same-sex marriage nationwide.', 'lgbtq_rights'),
  ('The Employment Non-Discrimination Act has been introduced in Congress multiple times but has never been signed into law.', 'lgbtq_rights'),
  ('Bostock v. Clayton County (2020) held that Title VII''s prohibition on sex discrimination covers sexual orientation and gender identity.', 'lgbtq_rights'),
  ('The Stonewall Uprising of 1969 is widely considered a pivotal catalyst for the modern LGBTQ+ civil rights movement in the United States.', 'lgbtq_rights'),
  ('The Respect for Marriage Act (2022) codified federal recognition of same-sex and interracial marriages into statutory law.', 'lgbtq_rights'),
  -- marijuana_legalization
  ('Marijuana was classified as a Schedule I controlled substance under the federal Controlled Substances Act of 1970.', 'marijuana_legalization'),
  ('More than 20 U.S. states have legalized recreational marijuana by ballot measure or legislation, while others permit only medical use.', 'marijuana_legalization'),
  ('Despite state-level legalization, marijuana remains illegal under federal law, creating legal tensions for banks and businesses.', 'marijuana_legalization'),
  ('The first U.S. state to legalize recreational marijuana by ballot measure was Colorado, followed by Washington state, both in 2012.', 'marijuana_legalization'),
  ('The DEA and FDA jointly determine whether a substance should be rescheduled under the federal Controlled Substances Act.', 'marijuana_legalization'),
  -- medicare
  ('Medicare was signed into law by President Lyndon B. Johnson in 1965 as part of the Social Security Amendments.', 'medicare'),
  ('Medicare Part A covers hospital inpatient care; Part B covers outpatient services; Part D covers prescription drugs.', 'medicare'),
  ('Medicare Advantage (Part C) allows beneficiaries to receive Medicare benefits through private insurers approved by the federal government.', 'medicare'),
  ('Medicare is funded primarily through payroll taxes, premiums paid by enrollees, and general federal revenues.', 'medicare'),
  ('Roughly 65 million Americans are enrolled in Medicare, including those 65 and older and some younger people with disabilities.', 'medicare'),
  -- military_veterans
  ('The Department of Veterans Affairs is one of the largest federal agencies, serving more than 9 million enrolled veterans.', 'military_veterans'),
  ('The GI Bill (Servicemen''s Readjustment Act of 1944) provided veterans with education, housing, and employment benefits after World War II.', 'military_veterans'),
  ('The VA healthcare system operates one of the largest networks of medical facilities in the United States.', 'military_veterans'),
  ('Post-9/11 GI Bill benefits cover full tuition at public universities and provide a housing stipend for eligible veterans.', 'military_veterans'),
  ('The Vietnam Veterans Memorial in Washington, D.C., dedicated in 1982, lists the names of over 58,000 service members killed or missing.', 'military_veterans'),
  -- minimum_wage
  ('The federal minimum wage has been $7.25 per hour since 2009, the longest period without an increase in its history.', 'minimum_wage'),
  ('The federal minimum wage was first established at $0.25 per hour under the Fair Labor Standards Act of 1938.', 'minimum_wage'),
  ('States and localities can set minimum wages above the federal floor; many have done so, with some exceeding $15 per hour.', 'minimum_wage'),
  ('Tipped workers are subject to a separate federal tipped minimum wage of $2.13 per hour if tips bring total pay to the standard minimum.', 'minimum_wage'),
  ('The Congressional Budget Office estimates that minimum wage increases tend to raise incomes for some workers while reducing jobs for others.', 'minimum_wage'),
  -- national_security
  ('The National Security Act of 1947 unified the military, created the CIA, and established the National Security Council.', 'national_security'),
  ('The intelligence community consists of 18 agencies and organizations, coordinated by the Office of the Director of National Intelligence.', 'national_security'),
  ('The USA PATRIOT Act, enacted after the September 11 attacks, significantly expanded law enforcement surveillance powers.', 'national_security'),
  ('NATO, founded in 1949, commits member nations to treat an armed attack on one member as an attack on all.', 'national_security'),
  ('The president is commander-in-chief of the U.S. armed forces, while Congress holds the power to declare war and fund the military.', 'national_security'),
  -- police_reform
  ('Police departments in the United States are overwhelmingly local institutions; there are roughly 18,000 separate law enforcement agencies.', 'police_reform'),
  ('The George Floyd Justice in Policing Act passed the House in 2021 but did not advance in the Senate.', 'police_reform'),
  ('Qualified immunity is a legal doctrine that can shield government officials, including police officers, from civil rights lawsuits.', 'police_reform'),
  ('Consent decrees between the Department of Justice and local police departments can require court-monitored reforms to policing practices.', 'police_reform'),
  ('The 1994 Violent Crime Control and Law Enforcement Act authorized federal grants that helped expand local police forces across the country.', 'police_reform'),
  -- prescription_drug_costs
  ('The Food and Drug Administration approves both brand-name drugs and generic equivalents after reviewing safety and efficacy data.', 'prescription_drug_costs'),
  ('The Inflation Reduction Act of 2022 authorized Medicare to negotiate prices for a limited set of high-cost prescription drugs.', 'prescription_drug_costs'),
  ('The Hatch-Waxman Act of 1984 created the regulatory pathway for generic drugs and established rules on brand-name patent protections.', 'prescription_drug_costs'),
  ('The U.S. pays significantly higher prices for brand-name prescription drugs than most other high-income nations.', 'prescription_drug_costs'),
  ('Pharmacy benefit managers (PBMs) act as intermediaries between insurers, pharmacies, and drug manufacturers in negotiating drug prices.', 'prescription_drug_costs'),
  -- privacy_surveillance
  ('The Fourth Amendment protects against unreasonable searches and seizures and generally requires a warrant based on probable cause.', 'privacy_surveillance'),
  ('The Foreign Intelligence Surveillance Act (FISA) of 1978 created a special court to oversee requests for surveillance of foreign agents.', 'privacy_surveillance'),
  ('The NSA mass phone-metadata collection program revealed by Edward Snowden in 2013 was later ruled illegal by a federal court.', 'privacy_surveillance'),
  ('The Electronic Communications Privacy Act of 1986 set the legal standards for government access to electronic communications and stored data.', 'privacy_surveillance'),
  ('No comprehensive federal data-privacy law exists in the United States; privacy protections are instead spread across many sector-specific laws.', 'privacy_surveillance'),
  -- public_transportation
  ('The Federal Transit Administration provides billions in grants annually to support local bus, rail, and other transit systems.', 'public_transportation'),
  ('Amtrak, the national passenger rail corporation, was created by Congress in 1970 and receives annual federal operating subsidies.', 'public_transportation'),
  ('The New York City subway, opened in 1904, is one of the oldest and largest metro rail systems in the world.', 'public_transportation'),
  ('The Americans with Disabilities Act requires that public transit systems be accessible to people with physical disabilities.', 'public_transportation'),
  ('Highway Trust Fund revenues from the federal gas tax have been the primary source of federal surface transportation funding since 1956.', 'public_transportation'),
  -- racial_justice
  ('The 13th Amendment, ratified in 1865, abolished slavery and involuntary servitude except as punishment for a crime.', 'racial_justice'),
  ('Redlining was the practice of denying services to residents of certain areas based on race; it was outlawed by the Fair Housing Act of 1968.', 'racial_justice'),
  ('Brown v. Board of Education (1954) held that racially segregated public schools are unconstitutional under the 14th Amendment.', 'racial_justice'),
  ('The Civil Rights Act of 1968 (Fair Housing Act) prohibited discrimination in the sale, rental, and financing of housing.', 'racial_justice'),
  ('The Kerner Commission Report (1968) concluded that the United States was "moving toward two societies, one black, one white — separate and unequal."', 'racial_justice'),
  -- social_security
  ('Social Security was signed into law by President Franklin D. Roosevelt in 1935 as part of the New Deal.', 'social_security'),
  ('Social Security is funded through dedicated payroll taxes paid by workers and employers under the Federal Insurance Contributions Act (FICA).', 'social_security'),
  ('The full retirement age for Social Security has been gradually rising from 65 to 67 for those born after 1943.', 'social_security'),
  ('Social Security pays benefits to retired workers, disabled individuals, and survivors of deceased workers and their families.', 'social_security'),
  ('Social Security is the single largest program in the federal budget, accounting for roughly one-quarter of total federal spending.', 'social_security'),
  -- student_debt
  ('Total outstanding federal student loan debt in the United States exceeds $1.7 trillion, held by more than 40 million borrowers.', 'student_debt'),
  ('Federal student loans are issued by the U.S. Department of Education; private student loans are issued by banks and other lenders.', 'student_debt'),
  ('The Public Service Loan Forgiveness program, created in 2007, cancels remaining federal loan balances after 10 years of qualifying public-sector work.', 'student_debt'),
  ('Income-driven repayment plans cap federal student loan payments at a percentage of the borrower''s discretionary income.', 'student_debt'),
  ('Unlike most other debt, federal student loans generally cannot be discharged through personal bankruptcy without proving undue hardship.', 'student_debt'),
  -- supreme_court
  ('The Supreme Court consists of nine justices — one Chief Justice and eight Associate Justices — though the Constitution does not specify this number.', 'supreme_court'),
  ('Marbury v. Madison (1803) established the principle of judicial review, giving federal courts the power to strike down unconstitutional laws.', 'supreme_court'),
  ('Supreme Court justices are nominated by the president and confirmed by the Senate; they serve lifetime appointments.', 'supreme_court'),
  ('The Supreme Court receives roughly 7,000 to 8,000 petitions each term but typically agrees to hear only 60 to 80 cases.', 'supreme_court'),
  ('The Court''s term begins on the first Monday of October and typically ends in late June or early July.', 'supreme_court'),
  -- tariffs_trade
  ('A tariff is a tax imposed by a government on imported goods, which raises the price of those goods for domestic consumers.', 'tariffs_trade'),
  ('The World Trade Organization (WTO), established in 1995, sets rules for international trade and provides a dispute-resolution mechanism.', 'tariffs_trade'),
  ('The Smoot-Hawley Tariff Act of 1930 raised tariffs on hundreds of goods and is widely associated with deepening the Great Depression.', 'tariffs_trade'),
  ('Most-favored-nation (MFN) status means a country grants another country the same trade terms it gives its most-favored trading partner.', 'tariffs_trade'),
  ('Congress delegated broad tariff-setting authority to the executive branch under the Trade Expansion Act of 1962 and subsequent legislation.', 'tariffs_trade'),
  -- taxes
  ('The 16th Amendment, ratified in 1913, gave Congress the authority to levy a federal income tax without apportioning it among the states.', 'taxes'),
  ('The IRS (Internal Revenue Service) is the federal agency responsible for collecting taxes and enforcing federal tax laws.', 'taxes'),
  ('The U.S. uses a progressive income tax system in which higher income is taxed at higher marginal rates.', 'taxes'),
  ('The Tax Cuts and Jobs Act of 2017 reduced the corporate tax rate from 35 percent to 21 percent and revised individual income tax brackets.', 'taxes'),
  ('Federal payroll taxes, which fund Social Security and Medicare, are paid by both employees and employers on wages up to annual caps.', 'taxes'),
  -- technology_regulation
  ('Section 230 of the Communications Decency Act (1996) generally shields online platforms from legal liability for user-generated content.', 'technology_regulation'),
  ('The Federal Trade Commission enforces antitrust and consumer protection laws and has authority to investigate large technology companies.', 'technology_regulation'),
  ('The Children''s Online Privacy Protection Act (COPPA, 1998) restricts online collection of personal information from children under 13.', 'technology_regulation'),
  ('No single comprehensive federal data-privacy law governs all technology companies; the U.S. instead relies on sector-specific rules.', 'technology_regulation'),
  ('The European Union''s GDPR (2018) is widely regarded as the strictest data-privacy regulation globally and has influenced U.S. debates.', 'technology_regulation'),
  -- voting_rights
  ('The 15th Amendment (1870) prohibited denying the right to vote based on race; the 19th Amendment (1920) extended that right to women.', 'voting_rights'),
  ('The Voting Rights Act of 1965 required certain states with histories of discrimination to obtain federal approval before changing voting rules.', 'voting_rights'),
  ('Shelby County v. Holder (2013) struck down the formula used to determine which states needed federal preclearance under the Voting Rights Act.', 'voting_rights'),
  ('Voter registration and election administration rules vary significantly from state to state; each state runs its own elections.', 'voting_rights'),
  ('The Help America Vote Act of 2002 mandated provisional ballots, improved voting systems, and established minimum federal election standards.', 'voting_rights'),
  -- wage_inequality
  ('The Gini coefficient is a statistical measure of income or wealth distribution within a population, where 0 means perfect equality.', 'wage_inequality'),
  ('The gender pay gap refers to the difference in median earnings between men and women across the workforce.', 'wage_inequality'),
  ('The Equal Pay Act of 1963 requires that men and women in the same workplace receive equal pay for substantially equal work.', 'wage_inequality'),
  ('CEO-to-worker pay ratios at large U.S. companies have grown substantially over the past several decades.', 'wage_inequality'),
  ('The top marginal federal income tax rate in the U.S. peaked at 91 percent in the 1950s and has fluctuated significantly since then.', 'wage_inequality'),
  -- water_resources
  ('The Clean Water Act of 1972 established the goal of eliminating pollutant discharges into U.S. navigable waters.', 'water_resources'),
  ('The Safe Drinking Water Act of 1974 authorizes the EPA to set standards for public drinking water quality across the country.', 'water_resources'),
  ('The Colorado River supplies water to about 40 million people across seven U.S. states and parts of Mexico.', 'water_resources'),
  ('Western U.S. water rights are governed largely by the prior appropriation doctrine ("first in time, first in right").', 'water_resources'),
  ('The Army Corps of Engineers and the Bureau of Reclamation are the two primary federal agencies that manage U.S. water infrastructure.', 'water_resources');
  END IF;
END
$migration$;
