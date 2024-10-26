-- Add grand_total column to adult_partners
ALTER TABLE adult_partners ADD COLUMN grand_total REAL;

-- Add grand_total column to children_partners
ALTER TABLE children_partners ADD COLUMN grand_total REAL;

-- Add grand_total column to teenager_partners
ALTER TABLE teenager_partners ADD COLUMN grand_total REAL;

-- Update existing records to calculate grand_total
UPDATE adult_partners 
SET grand_total = total_wonder_challenge + total_rhapsody_languages + 
    total_kiddies_products + total_teevo + total_braille_nolb + 
    total_youth_aglow + total_local_distribution + total_subscriptions_dubais;

UPDATE children_partners 
SET grand_total = total_wonder_challenge + total_rhapsody_languages + 
    total_kiddies_products + total_teevo + total_braille_nolb + 
    total_youth_aglow + total_local_distribution + total_subscriptions_dubais;

UPDATE teenager_partners 
SET grand_total = total_wonder_challenge + total_rhapsody_languages + 
    total_kiddies_products + total_teevo + total_braille_nolb + 
    total_youth_aglow + total_local_distribution + total_subscriptions_dubais;
