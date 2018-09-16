---
title: "About"
type: pages
layout: splash
header:
  image: /assets/images/index_page/header.jpg
author_profile: true
permalink: /

feature_row_publications:
 - image_path: /assets/images/index_page/publication_iq.png
   alt: "Poster Presentation at ISMRM 2018"
   title: "Poster Presentation at ISMRM 2018"
   excerpt: "S. Braun, X. Chen, B. Odry, B. Mailhe, M. Nadar, “Motion Detection and Quality Assessment of MR images with Deep Convolutional DenseNets”, Proc. Intl. Soc. Mag. Reson. Med. 26:2715 (2018), Paris"
   url: "http://indexsmart.mirasmart.com/ISMRM2018/PDFfiles/2715.html"
   btn_label: "Read Publication"
   btn_class: "btn--inverse"

 - image_path: /assets/images/index_page/publication_moco.png
   alt: "Poster Presentation at ISMRM 2018"
   title: "Poster Presentation at ISMRM 2018"
   excerpt: "S. Braun, P. Ceccaldi, X. Chen, B. Odry, B. Mailhe, M. Nadar, “Wasserstein GAN for Motion Artifact Reduction of MR images”, Proc. Intl. Soc. Mag. Reson. Med. 26:4093 (2018), Paris"
   url: "http://indexsmart.mirasmart.com/ISMRM2018/PDFfiles/4093.html"
   btn_label: "Read Publication"
   btn_class: "btn--inverse"     

 - image_path: /assets/images/index_page/thesis_LF.png
   alt: "Bachelor Thesis"
   title: "Bachelor Thesis"
   excerpt: "German title: Simulation einer Lichtfeld Kamera mit Blendenmodulation. English translation: Simulation of lightfield cameras using aperture modulation."
   url: "https://www.dropbox.com/s/afq30s1223xrel9/SimulationEinerLichtfeldKameraMitBlendenmodulation.pdf?dl=0"
   btn_label: "Read Thesis (German)"
   btn_class: "btn--inverse" 

feature_row_teaching:
 - image_path: /assets/images/index_page/teaching_dlws.jpg
   alt: "Deep Learning Workshop"
   title: "Deep Learning Workshop"
   excerpt: "A workshop I did through Hack & Söhne together with Maximilian Franz and Leander Kurscheidt. We wanted to make very low level concepts clear and not just do   tensorflow.train()."
   btn_label: "Workshop Website"
   btn_class: "btn--inverse"   
   url: "https://hackundsoehne.de/deeplearning"

 - image_path: /assets/images/index_page/teaching_titraa.png
   alt: "TiTrAa Workshop"
   title: "TiTrAa Workshop"
   excerpt: "After my bachelor thesis I was frustrated that the writing workflow is so  hard to learn. That’s why I made a workshop about it. Why is it called TiTrAa? TiTrAa stands for 'Tipps und Tricks zu Abschlussarbeit' and is German for 'thesis workflow hacks'."
   url: "https://github.com/theRealSuperMario/titraa_public/blob/master/MARKDOWN/index.markdown"
   btn_label: "View on Github"
   btn_class: "btn--inverse"

 - image_path: /assets/images/index_page/teaching_linuxws.png
   alt: "Linux Workshops"
   title: "Linux Workshops"
   excerpt: "I gave Linux Workshops at AKK Karlsruhe."
   url: "https://github.com/theRealSuperMario/LinuxWorkshop"
   btn_label: "View on Github"
   btn_class: "btn--inverse"   

 - image_path: /assets/images/index_page/teaching_math_export.png
   alt: "Mathematics Tutorials"
   title: "Mathematics Tutorials"
   excerpt: "I gave math tutorials from 2014 to 2016. It is important to get feedback about your teaching methods which is why I wrote an app to monitor the quality of my tutorials."
   url: "/mathTutorials/"
   btn_label: "Tutorials Website"
   btn_class: "btn--inverse"  

feature_row_activities:
 - image_path: /assets/images/index_page/activities_och.jpg
   alt: "Open Codes Hackathon"
   title: "Open Codes Hackathon"
   excerpt: "I was part of the organizer team and a speaker for the Open Codes Hackathon. The Open Codes Hackathon was the largest student-run hackathon in Germany with international 200 participants."
   url: "https://opencodes.io/"
   btn_label: "Official Hackathon Website"
   btn_class: "btn--inverse"

 - image_path: /assets/images/index_page/activities_theoryPDG.jpg
   alt: "Machine Learning Karlsruhe"
   title: "Machine Learning Karlsruhe"
   excerpt: "ML-KA hosts weekly paper discussions group meetings (PDG) about Machine Learning. The classic pdg is Wednesdays. We recently started a theory-PDG branch that focusses on theoretical aspects of Machine Learning."
   url: "https://github.com/ML-KA/PDG-Theory"
   btn_label: "Theory PDG on Github"
   btn_class: "btn--inverse"   

 - image_path: /assets/images/index_page/activities_photo.jpg
   alt: "Photo Gallery"
   title: "Photo Gallery"
   excerpt: "I have a passion for photography. Check out my gallery."
   url: "/photos/"
   btn_label: "Photo Gallery"
   btn_class: "btn--inverse"       

---


# Hi! My name is Sandro


![align-left]({{ site.url }}{{ site.baseurl }}/assets/images/index_page/avatar.jpg){: .align-left}
I'm a Master student at Karlsruhe Institute of Technology with a background in signal processing.
I have past experience on computational cameras and displays, image quality assessment and motion artefact reduction in magnetic resonance images and deep learning. 

Currently, I am focussing on more theoretical parts of machine learning while increasing my hands-on experience through semantic segmentation of lidar data.

In my spare time I organize events through [Hack & Söhne](https://hackundsoehne.de/ "Hack & Soehne Website") and [take photos](/photos/ "Check out my gallery").
[Follow me on github](https://github.com/therealsupermario "Sandro on Github").
<br>
<br>

---
---

# Publications and Projects

{% include feature_row id="feature_row_publications" %}

# Teaching and Workshops

{% include feature_row id="feature_row_teaching" %}

# Some other things I do and did

{% include feature_row id="feature_row_activities" %}