import cv2
import numpy as np

orb = cv2.ORB_create()
img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
kp, des1 = orb.detectAndCompute(img, None)

des_list = des1.tolist()
des2 = np.array(des_list, dtype=np.uint8)

bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
try:
    matches = bf.match(des1, des2)
    print("Match successful, length:", len(matches))
except Exception as e:
    print("Match failed:", e)
