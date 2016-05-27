import numpy as np
import cv2
import collections
import datetime
import time
import itertools

Image = collections.namedtuple("Image","raw_image detection_center timestamp")

try:
    import urllib.request as urllib
    import urllib.error as url_error
    PYTHON2 = False
except ImportError:
    import urllib
    import urllib2
    import urllib2 as url_error
    PYTHON2 = True

class IPCam():

    def __init__(self,ip,user,password, threshold = 8, max_detection_area = 1000, debug=False):

        self.cam_url = 'http://{0}/'.format(ip)
        self.debug = debug
        self.max_detection_area = max_detection_area
        self.threshold = threshold
        # Try to connect to the cam and create the streamer
        if PYTHON2:
            password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None,self.cam_url, user, password )
            handler = urllib2.HTTPBasicAuthHandler(password_mgr)
            self.opener = urllib2.build_opener(handler)
        else:
            password_mgr = urllib.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None,self.cam_url, 'admin', 'uffdr1')
            handler = urllib.HTTPBasicAuthHandler(password_mgr)
            self.opener = urllib.build_opener(handler)

        if not self.test_connection():
            raise url_error("|| Cannot comunicate with camera ||")


    def test_connection(self):
        """
        Test the connection with the IP cam using a simple HTTP GET method.
        """
        try:
            simple_image_url = self.cam_url + 'image/jpeg.cgi'
            self.opener.open( simple_image_url )
            return True
        except url_error.URLError:
            return False

    def get_simple_frame(self):

        simple_image_url = self.cam_url + 'image/jpeg.cgi'
        simple_image = self.opener.open( simple_image_url )
        return simple_image.read()

    def raw_video_stream(self):
        """
        Get a generator that yields raw images (in byte format) from the IP Cam in real time.

        Output: raw_image
        """
        # Get raw video stream
        raw_byte_stream =  self.opener.open('http://192.168.1.131/video/mjpg.cgi')

        # Extract frames from raw_video_stream
        count = itertools.count()
        fails = next(count)
        if PYTHON2:
            byte_stream=''
            while True:
                byte_stream+=raw_byte_stream.read(16384)
                if self.debug:
                    print('Frame recieved. Start Transformation')
                a = byte_stream.find('\xff\xd8')
                b = byte_stream.find('\xff\xd9')

                print(a,b)

                if fails > 10:
                    raise ValueError('10 fails locating b')

                if a!=-1 and b!=-1:
                    raw_image = byte_stream[a:b+2]
                    byte_stream= byte_stream[b+2:]
                    yield raw_image
                else:
                    fails = next(count)
        else:
            byte_stream = bytes()
            while True:
                byte_stream+=raw_byte_stream.read(16384)
                if self.debug:
                    print('Frame recieved. Start Transformation')
                a = byte_stream.find(b'\xff\xd8')
                b = byte_stream.find(b'\xff\xd9')

                print(a,b)

                if fails > 10:
                    raise ValueError('10 fails locating b')

                if a!=-1 and b!=-1:
                    raw_image = byte_stream[a:b+2]
                    byte_stream= byte_stream[b+2:]
                    yield raw_image
                else:
                    fails = next(count)

    def video_stream(self,mixed = False):
        """
        Get a generator that yields images as numpy arrays from the IP Cam in real time.

        If mixed is True, also yields the raw image that was used to generate the numpy array.

        Output: raw_image, numpy_array

        Note: If mixed = False then raw_image = None.
        """

        if mixed:
            for raw_frame in self.raw_video_stream():
                yield raw_frame, cv2.imdecode(np.fromstring(raw_frame, dtype=np.uint8),cv2.IMREAD_COLOR)
        else:
            for raw_frame in self.raw_video_stream():
                yield None, cv2.imdecode(np.fromstring(raw_frame, dtype=np.uint8),cv2.IMREAD_COLOR)

    def motion_detector_steamer(self, raw_frame = True, view_stream = False):
        """
        Get a generator that yields the centroid of the moving objects from the IP Cam in real time.

        If raw_frame is True then also yields the raw_image used for the calculation.

        If view_stream is True then a window is open for visualizing the process.

        Output: raw_frame, centroid

        Note: centroid is None if no motion is detected.
        Note: raw_frame is always the last frame with detection or the first frame if no motion has been detected yet.
        """
        background = None
        debug = self.debug
        timer = time.time

        for raw_frame, frame in self.video_stream(mixed=raw_frame):

            start_timer = timer()

            if self.debug:
                print('Start Computation')
            # Get timestamp

            timestamp = datetime.datetime.now()

            # resize the frame, convert it to grayscale, and blur it
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)


            # if the average frame is None, initialize it
            if background is None:
                background = gray.copy().astype("float")
                last_frame = raw_frame
                continue

            # accumulate the weighted average between the current frame and
            # previous frames, then compute the difference between the current
            # frame and running average
            cv2.accumulateWeighted(gray, background , 0.5)
            frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(background))
            # threshold the delta image, dilate the thresholded image to fill
            # in holes, then find contours on thresholded image
            thresh = cv2.threshold(frameDelta, self.threshold , 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            (image, contours , hierarchy) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                                             cv2.CHAIN_APPROX_SIMPLE)

            # Prepare list of centers for x and y

            x_means = []
            y_means = []

            if self.debug:
                print('Detecting contours')

            for contour in contours:
                # Ignore small contours
                if cv2.contourArea(contour) < self.max_detection_area:
                    continue
                # get center of contour and append to list of contours
                moments = cv2.moments(contour)
                x_means.append( int(moments['m10']/moments['m00']) )
                y_means.append( int(moments['m01']/moments['m00']) )

                # Make the mean of the contours and yield this center with the raw image
            if x_means and y_means:
                last_frame = raw_frame
                yield Image(last_frame,(np.mean(x_means),np.mean(y_means)),timestamp)

                # Add circle if view_stream is True
                if view_stream:
                    cv2.circle(frame, (int(np.mean(x_means)),int(np.mean(y_means))),15, (0, 255, 0))
            else:
                yield Image(last_frame,None,timestamp)
            if debug:
                print("Frame computed in {} seconds".format(timer() - start_timer))


            if view_stream:
                cv2.imshow("Feed",frame)
                key = cv2.waitKey(1) & 0xFF
                # if the `q` key is pressed, break from the lop
                if key == ord("q"):
                    break
