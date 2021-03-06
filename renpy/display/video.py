# Copyright 2004-2016 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import renpy.display
import renpy.audio
import collections

# The movie displayable that's currently being shown on the screen.
current_movie = None

# True if the movie that is currently displaying is in fullscreen mode,
# False if it's a smaller size.
fullscreen = False

# The size of a Movie object that hasn't had an explicit size set.
default_size = (400, 300)

# The file we allocated the surface for.
surface_file = None

# The surface to display the movie on, if not fullscreen.
surface = None

def movie_stop(clear=True, only_fullscreen=False):
    """
    Stops the currently playing movie.
    """

    if (not fullscreen) and only_fullscreen:
        return

    renpy.audio.music.stop(channel='movie')


def movie_start(filename, size=None, loops=0):
    """
    This starts a movie playing.
    """

    if renpy.game.less_updates:
        return

    global default_size

    if size is not None:
        default_size = size

    filename = [ filename ]

    if loops == -1:
        loop = True
    else:
        loop = False
        filename = filename * (loops + 1)

    renpy.audio.music.play(filename, channel='movie', loop=loop)

movie_start_fullscreen = movie_start
movie_start_displayable = movie_start


# A map from a channel name to the movie texture that is being displayed
# on that channel.
texture = { }

# The set of channels that are being displayed in Movie objects.
displayable_channels = collections.defaultdict(list)

# A map from a channel to the topmost Movie being displayed on
# that channel. (Or None if no such movie exists.)
channel_movie = { }

# Same thing, but for the last time the screen was rendered.
old_channel_movie = { }

# Is there a video being displayed fullscreen?
fullscreen = False

def early_interact():
    """
    Called early in the interact process, to clear out the fullscreen
    flag.
    """

    displayable_channels.clear()
    channel_movie.clear()


def interact():
    """
    This is called each time the screen is drawn, and should return True
    if the movie should display fulscreen.
    """

    global fullscreen

    for i in list(texture.keys()):
        if not renpy.audio.music.get_playing(i):
            del texture[i]



    if renpy.audio.music.get_playing("movie"):

        for i in displayable_channels.keys():
            if i[0] == "movie":
                fullscreen = False
                break
        else:
            fullscreen = True

    else:
        fullscreen = False

    return fullscreen


def get_movie_texture(channel, mask_channel=None):

    if not renpy.audio.music.get_playing(channel):
        return None, False

    c = renpy.audio.music.get_channel(channel)
    surf = c.read_video()

    if mask_channel:
        mc = renpy.audio.music.get_channel(mask_channel)
        mask_surf = mc.read_video()
    else:
        mask_surf = None

    if mask_channel:

        # Something went wrong with the mask video.
        if surf and mask_surf:
            renpy.display.module.alpha_munge(mask_surf, surf, renpy.display.im.identity)
        else:
            surf = None

    if surf is not None:
        renpy.display.render.mutated_surface(surf)
        tex = renpy.display.draw.load_texture(surf, True)
        texture[channel] = tex
        new = True
    else:
        tex = texture.get(channel, None)
        new = False

    return tex, new

def render_movie(channel, width, height):
    tex, _new = get_movie_texture(channel)

    if tex is None:
        return None

    sw, sh = tex.get_size()

    scale = min(1.0 * width / sw, 1.0 * height / sh)

    dw = scale * sw
    dh = scale * sh

    rv = renpy.display.render.Render(width, height)
    rv.forward = renpy.display.render.Matrix2D(1.0 / scale, 0.0, 0.0, 1.0 / scale)
    rv.reverse = renpy.display.render.Matrix2D(scale, 0.0, 0.0, scale)
    rv.blit(tex, (int((width - dw) / 2), int((height - dh) / 2)))

    return rv


class Movie(renpy.display.core.Displayable):
    """
    :doc: movie

    This is a displayable that shows the current movie.

    `fps`
        The framerate that the movie should be shown at. (This is currently
        ignored, but the parameter is kept for backwards compatibility.
        The framerate is auto-detected.)

    `size`
        This should be specified as either a tuple giving the width and
        height of the movie, or None to automatically adjust to the size
        of the playing movie. (If None, the displayable will be (0, 0)
        when the movie is not playing.)

    `channel`
        The audio channel associated with this movie. When a movie file
        is played on that channel, it wil be displayed in this Movie
        displayable.

    `play`
        If given, this should be the path to a movie file. The movie
        file will be automatically played on `channel` when the Movie is
        shown, and automatically stopped when the movie is hidden.

    `mask`
        If given, this should be the path to a movie file that is used as
        the alpha channel of this displayable. The movie file will be
        automatically played on `movie_channel` when the Movie is shown,
        and automatically stopped when the movie is hidden.

    `mask_channel`
        The channel the alpha mask video is played on. If not given,
        defaults to `channel`_mask. (For example, if `channel` is "sprite",
        `mask_channel` defaults to "sprite_mask".)

    `image`
        An image that is displayed when `play` has been given, but the
        file it refers to does not exist. (For example, this can be used
        to create a slimmed-down mobile version that does not use movie
        sprites.)

    This displayable will be transparent when the movie is not playing.
    """

    fullscreen = False
    channel = "movie"
    _play = None

    mask = None
    mask_channel = None

    image = None

    def ensure_channel(self, name):

        if name is None:
            return

        if renpy.audio.music.channel_defined(name):
            return

        renpy.audio.music.register_channel(name, renpy.config.movie_mixer, loop=True, stop_on_mute=False, movie=True)

    def __init__(self, fps=24, size=None, channel="movie", play=None, mask=None, mask_channel=None, image=None, **properties):
        super(Movie, self).__init__(**properties)
        self.size = size
        self.channel = channel
        self._play = play

        self.mask = mask

        if mask is None:
            self.mask_channel = None
        elif mask_channel is None:
            self.mask_channel = channel + "_mask"
        else:
            self.mask_channel = mask_channel

        self.ensure_channel(self.channel)
        self.ensure_channel(self.mask_channel)

        self.image = renpy.easy.displayable_or_none(image)

        if (self.channel == "movie") and (renpy.config.hw_video) and renpy.mobile:
            raise Exception("Movie(channel='movie') doesn't work on mobile when config.hw_video is true. (Use a different channel argument.)")

    def render(self, width, height, st, at):

        if (self.image is not None) and (self._play is not None) and (not renpy.loader.loadable(self._play)):
            surf = renpy.display.render.render(self.image, width, height, st, at)

            w, h = surf.get_size()

            rv = renpy.display.render.Render(w, h)
            rv.blit(surf, (0, 0))

            return rv

        if self._play:
            channel_movie[self.channel] = self

        playing = renpy.audio.music.get_playing(self.channel)

        if self.size is None:

            tex, _ = get_movie_texture(self.channel, self.mask_channel)

            if playing and (tex is not None):
                width, height = tex.get_size()

                rv = renpy.display.render.Render(width, height)
                rv.blit(tex, (0, 0))

            else:
                rv = renpy.display.render.Render(0, 0)

        else:

            w, h = self.size

            if not playing:
                rv = None
            else:
                rv = render_movie(self.channel, w, h)

            if rv is None:
                rv = renpy.display.render.Render(w, h)

        # Usually we get redrawn when the frame is ready - but we want
        # the movie to disappear if it's ended, or if it hasn't started
        # yet.
        renpy.display.render.redraw(self, 0.1)

        return rv

    def play(self, old):
        if old is None:
            old_play = None
        else:
            old_play = old._play

        if self._play != old_play:
            if self._play:
                renpy.audio.music.play(self._play, channel=self.channel, loop=True, synchro_start=True)

                if self.mask:
                    renpy.audio.music.play(self.mask, channel=self.mask_channel, loop=True, synchro_start=True)

            else:
                renpy.audio.music.stop(channel=self.channel)

                if self.mask:
                    renpy.audio.music.stop(channel=self.mask_channel)

    def stop(self):
        if self._play:
            renpy.audio.music.stop(channel=self.channel)

            if self.mask:
                renpy.audio.music.stop(channel=self.mask_channel)


    def per_interact(self):
        displayable_channels[(self.channel, self.mask_channel)].append(self)
        renpy.display.render.redraw(self, 0)


def playing():
    if renpy.audio.music.get_playing("movie"):
        return True

    for i in displayable_channels:
        channel, _mask_channel = i

        if renpy.audio.music.get_playing(channel):
            return True

def update_playing():
    """
    Calls play/stop on Movie displayables.
    """

    global old_channel_movie

    for c, m in channel_movie.items():
        old = old_channel_movie.get(c, None)

        if old is not m:
            m.play(old)

    for c, m in old_channel_movie.items():
        if c not in channel_movie:
            m.stop()

    old_channel_movie = dict(channel_movie)

def frequent():
    """
    Called to update the video playback. Returns true if a video refresh is
    needed, false otherwise.
    """

    update_playing()

    renpy.audio.audio.advance_time()

    if displayable_channels:

        update = True

        for i in displayable_channels:
            channel, mask_channel = i

            c = renpy.audio.audio.get_channel(channel)
            if not c.video_ready():
                update = False
                break

            if mask_channel:
                c = renpy.audio.audio.get_channel(mask_channel)
                if not c.video_ready():
                    update = False
                    break

        if update:
            for v in displayable_channels.values():
                for j in v:
                    renpy.display.render.redraw(j, 0.0)

        return False

    elif fullscreen and not (renpy.mobile and renpy.config.hw_video):

        c = renpy.audio.audio.get_channel("movie")

        if c.video_ready():
            return True
        else:
            return False

    return False
