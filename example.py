import time
from sound_player import Sound, Playlist, SoundPlayer


def test_sound():
    print("Test sound:")
    sound = Sound("data/music.ogg")

    sound.play()
    time.sleep(3)

    sound.pause()
    time.sleep(2)

    sound.play()
    time.sleep(3)

    sound.stop()
    time.sleep(2)


def test_playlist():
    print("Test playlist")
    pl = Playlist(concurency=2)
    pl.enqueue(Sound("data/coin.wav"))
    pl.enqueue(Sound("data/music.ogg"))
    pl.enqueue(Sound("data/coin.wav"))
    pl.enqueue(Sound("data/coin.wav"))

    pl.play()
    time.sleep(10)
    pl.stop()
    time.sleep(2)


def test_sound_player():
    print("Test player")
    player = SoundPlayer()
    # first player
    player.enqueue(Sound("data/coin.wav"), 1)
    player.enqueue(Sound("data/music.ogg"), 1)
    player.enqueue(Sound("data/coin.wav"), 1)

    player.play()
    time.sleep(5)

    # second player
    player.enqueue(Sound("data/coin.wav"), 2)
    player.enqueue(Sound("data/coin.wav"), 2)
    time.sleep(10)
    player.stop()
    time.sleep(1)


if __name__ == "__main__":
    #test_sound()
    #test_playlist()
    test_sound_player()
