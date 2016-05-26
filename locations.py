import tracker

def room_location( center ):

    if not center:
        return None

    x,y = center

    if 457<= x <= 584 and 90<= y <= 207:
        return "En casa circular"
    elif 189<= x <= 311 and 94<= y <= 187:
        return "En el bebedero"
    elif 0<= x <= 135 and 0<= y <= 211:
        return "Mirador del rascador"
    elif 114<= x <= 222 and 246 <= y <= 352:
        return "Balda circular del rascador"
    elif 236<= x <= 639 and 225 <= y <= 352:
        return "En el suelo"
    elif 305<= x <= 471 and 98 <= y <= 209:
        return "En el suelo"
if __name__ == '__main__':
    import cv2
    import itertools
    streamer = tracker.get_coordinates()

    time_in_location = 0
    last_location = None

    for center,frame in streamer:
        center = room_location(center)
        if center and center != last_location:
            last_location = center
            time_in_location = 0
            print()
            print(center)
            cv2.imshow("Feed",frame)
            key = cv2.waitKey(1) & 0xFF
        else:
            time_in_location += 1
            print('\rTime in location: {}'.format(time_in_location),end="")
