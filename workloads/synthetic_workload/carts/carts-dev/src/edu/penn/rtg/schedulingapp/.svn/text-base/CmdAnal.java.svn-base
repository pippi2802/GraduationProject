package edu.penn.rtg.schedulingapp;


import edu.penn.rtg.schedulingapp.input.xml.XMLInterpreter;
import edu.penn.rtg.schedulingapp.output.XMLOutput;
import edu.penn.rtg.schedulingapp.output.graph.GenGraph;
import edu.penn.rtg.schedulingapp.util.CartsProgress;

public class CmdAnal {
	public static void process(String[] args) {
		
		if (args.length < 3) {
			error();
		} else {
			try {
				run(args[0],args[1],args[2]);
			} catch (Exception e) {
				//e.printStackTrace();
				System.err.println("Invalid CARTS XML file " + args[0]);
			}
		}
	}
	private static void run(String input,String algo,String output) throws Exception {
		CartsProgress.isApp=true;
		System.out.println("reading input: "+input);
		XMLInterpreter inter = new XMLInterpreter(input);
		if(!inter.readFile()){
			System.out.println(inter.getErrorMsg());
			System.exit(1);
		}
		SchedulingTree scTree = inter.getScTree();
		TreeComponent root=scTree.getRoot();
		GenGraph.isApp=true;
		System.out.println("input algorithm: "+algo);
		String rs=Analysis.preProcess(algo,root );
		if(rs==null) {
			System.out.println("Operation is canceled");
			System.exit(0);
		}
		if(rs.equals("ERR")) {
			errorAlgo();
			System.exit(1);
		}
		System.out.println("processed algorithm: "+rs);
		XMLOutput.writeOutput(root,output,rs);
		System.out.println("output is written: "+output);
		
	}
	private static void error() {
		System.err.println("Invalid arguments");
		System.err
				.println("Carts <input_XML_file> <scheduling_algo> <output_XML_file>");
		errorAlgo();
	}
	private static void errorAlgo() {
		System.err
				.println("<scheduling_algo> can be : PRM / EDP / MPR / DPRM / EQV");
	}

}
