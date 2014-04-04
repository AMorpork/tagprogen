import os
import random
from itertools import product
import uuid
import itertools

from dijkstar import Graph, find_path, NoPathError
from PIL import Image
from PIL.ImageDraw import ImageDraw

# Configurable settings
min_pass_count = 10  # Minimum and maximum number of passes to make.
max_pass_count = 15  # The more passes, the smoother it will be.
wall_chance = .525  # The chance of a wall appearing in the initial generation.
constant_symmetry = False  # Makes it symmetric on each pass.
output_folder = "generated/"  # The folder to output images into.
level_count = 100  # The number of images to generate.
min_floorspace = .3  # The minimum and maximum percentage of floor tiles.
max_floorspace = .8
draw_computed_path = True # Overlay the computed path on the output image.


class GenerationError(Exception):
    pass


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]


class Block:
    __metaclass__ = Singleton

    def __init__(self):
        self.image = Image.open(self.image_loc)


class Flag(Block):
    pass


class Floor(Block):
    image_loc = "floor.png"


class RedFlag(Flag):
    image_loc = "red_flag.png"


class BlueFlag(Flag):
    image_loc = "blue_flag.png"


class Wall(Block):
    image_loc = "wall.png"


class Level:
    def __init__(self, width=40, height=40):
        self.width = width
        self.height = height
        self.base_blocks = (Floor, Wall)
        self.grid = [[self.get_cell() for _ in range(width)]
                     for _ in range(height)]

    def get_neighbor_coords(self, x, y):
        xi = (0, -1, 1) if 0 < x < len(self.grid) - 1 else (
            (0, -1) if x > 0 else (0, 1))
        yi = (0, -1, 1) if 0 < y < len(self.grid[0]) - 1 else (
            (0, -1) if y > 0 else (0, 1))
        return [(x + a, y + b) for a, b in product(xi, yi)]

    def get_neighbors(self, x, y):
        return [self.grid[a][b] for a, b in self.get_neighbor_coords(x, y)]

    def run_pass(self):
        for x, y in product(range(self.width), range(self.height)):
            neighbors = self.get_neighbors(x, y)
            wall_count = 0
            for neighbor in neighbors:
                if isinstance(neighbor, Wall):
                    wall_count += 1
            if wall_count >= 5 and random.random() > 0.025:
                self.grid[x][y] = Wall()
            else:
                self.grid[x][y] = Floor()
        self.grid[0] = [Wall() for _ in range(self.height)]
        self.grid[-1] = [Wall() for _ in range(self.height)]
        for x in range(self.height):
            self.grid[x][0] = Wall()
            self.grid[x][-1] = Wall()

    def symmetrize(self):
        s = self.height // 2
        y = self.grid[0:s]
        z = [a for a in reversed(y)]
        for a in range(len(z)):
            z[a] = list(reversed(z[a]))
        y.extend(z)
        self.grid = y

    def make_image(self, flag_path=None):
        image = Image.new("RGBA", (self.width * 40, self.height * 40))
        filename = "{}.png".format(uuid.uuid4())
        path = os.path.join(output_folder, filename)
        for x in range(self.width):
            for y in range(self.height):
                cell = self.grid[x][y]
                image.paste(cell.image, (x * 40, y * 40))
        if flag_path is not None and draw_computed_path:
            self.draw_flag_path(image, flag_path)
        try:
            image.save(path)
        except KeyboardInterrupt:
            if os.path.isfile(path):
                os.remove(path)  # Perform cleanup to avoid a broken PNG.
            raise

    def flag_check(self):
        for x, y in product(range(self.width), range(self.height)):
            if isinstance(self.grid[x][y], Floor):
                pairs = (-1, -1, 0, 0, 1, 1)
                sums = itertools.permutations(pairs, 2)
                neighbors = [isinstance(z, Floor) for z in
                             itertools.chain.from_iterable(
                                 [self.get_neighbors(x + a, y + b) for a, b
                                  in sums])]
                if all(neighbors):
                    break
        else:
            raise GenerationError("Couldn't find a usable path.")
        return x, y

    def place_flags(self):
        x, y = self.flag_check()
        self.grid[-2 - x][-2 - y] = BlueFlag()
        self.grid[x + 1][y + 1] = RedFlag()


    def flood_fill(self, x, y, o):
        to_fill = set()
        to_fill.add((x, y))
        while len(to_fill) > 0 and (x < self.width and y < self.height):
            x, y = to_fill.pop()
            if not isinstance(self.grid[x][y], Floor):
                continue
            a = (x - 1, y)
            b = (x + 1, y)
            c = (x, y - 1)
            d = (x, y + 1)
            if a not in o:
                to_fill.add(a)
            if b not in o:
                to_fill.add(b)
            if c not in o:
                to_fill.add(c)
            if d not in o:
                to_fill.add(d)
            o = o.union(to_fill.copy())
        per = float(len(o)) / float(self.width * self.height)
        if per < min_floorspace:
            raise GenerationError("Not enough open space.")
        elif per > max_floorspace:
            raise GenerationError("Too much open space.")
        return o

    def remove_isolates(self):
        while True:
            a = set()
            b = set()
            x1 = random.randrange(0, self.width)
            x2 = random.randrange(0, self.width)
            y1 = random.randrange(0, self.height)
            y2 = random.randrange(0, self.height)
            n1 = self.flood_fill(x1, y1, a)
            n2 = self.flood_fill(x2, y2, b)
            if n1 == n2:
                break
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) not in n1:
                    self.grid[x][y] = Wall()

    def get_cell(self):
        x = random.random()
        if x <= wall_chance:
            return Wall()
        else:
            return Floor()

    def make_graph(self):
        graph = Graph()
        for x, y in product(range(self.width), range(self.height)):
            if isinstance(self.grid[x][y],
                          Floor) or isinstance(self.grid[x][y], Flag):
                for i, j in [(x + i, y + j) for i, j in
                             ((-1, 0), (1, 0), (0, 1), (0, -1))]:
                    if isinstance(self.grid[i][j],
                                  Floor) or isinstance(self.grid[i][j], Flag):
                        graph.add_edge((x, y), (i, j), 1)
        return graph

    def ensure_traversable(self):
        graph = self.make_graph()
        blue = None
        red = None
        for x, y in product(range(self.width), range(self.height)):
            cell = self.grid[x][y]
            if isinstance(cell, BlueFlag):
                blue = (x, y)
            elif isinstance(cell, RedFlag):
                red = (x, y)
            if blue is not None and red is not None:
                break
        path = find_path(graph, blue, red)
        return path

    def draw_flag_path(self, image, flag_path):
        flag_path = flag_path[0]
        pen = ImageDraw(image)
        x = 0
        while x < len(flag_path) - 1:
            x1, y1 = flag_path[x]
            x2, y2 = flag_path[x + 1]
            pen.line(((x1 * 40) + 20, (y1 * 40) + 20, (x2 * 40) + 20,
                      (y2 * 40) + 20), "yellow", width=4)
            x += 1


def generate_level(x=40, y=40):
    z = Level(x, y)
    for x in range(random.randrange(min_pass_count, max_pass_count)):
        if constant_symmetry:
            z.symmetrize()
        z.run_pass()
    z.remove_isolates()
    z.symmetrize()
    z.place_flags()
    flag_path = z.ensure_traversable()
    z.make_image(flag_path)


if __name__ == "__main__":
    print "Starting batch generation of {} levels".format(level_count)
    n = 1
    while n <= level_count:
        try:
            generate_level(30, 30)
            print "Level generated! {}/{} complete\n\n".format(n, level_count)
            n += 1
        except NoPathError, e:
            print "No path between flags. Restarting."
        except GenerationError, e:
            print "Recoverable Error: {}. Restarting.".format(e)