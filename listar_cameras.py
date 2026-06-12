import cv2

for i in range(5):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    
    if cap.isOpened():
        print(f"✅ Câmera encontrada no índice {i}")
        
        ret, frame = cap.read()
        if ret:
            cv2.imshow(f"Camera {i}", frame)
            cv2.waitKey(1000)  # mostra por 1 segundo
        
        cap.release()
    else:
        print(f"❌ Índice {i} não funciona")

cv2.destroyAllWindows()