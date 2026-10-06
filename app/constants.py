# NOTE (2026-10-02): Pehle yahan `INDIAN_STATES` (36 states/UT ki hardcoded list)
# thi, jo Vendor / Customer / Branch ke dropdowns use karte the. Woh list ab
# hata di gayi hai — States ka single source of truth **State Master** hai
# (`State` model / `states` table). Dropdowns ab `State.query` se aate hain aur
# Vendor / Customer / Branch me `state_id` FK store hota hai.
#
# (Seed migration `fd2c563b95f7` ne `states` table me 36 states/UT + GST codes
#  isi purani list ke order me bhar diye the, taaki purana text data match ho jaaye.)
