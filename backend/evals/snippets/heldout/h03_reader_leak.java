import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;

class Report {
    String firstLine(String path) throws IOException {
        // expect: bug|smell
        BufferedReader reader = new BufferedReader(new FileReader(path));
        return reader.readLine();
    }
}
